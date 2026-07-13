"""Single-slot async job runner + live streaming + local run history.

Execution model (DESIGN.md §5.3): ONE job at a time. main.py's build_subprocess_env
caps BLAS/OpenMP threads precisely because oversubscribing a resource-constrained
machine has stalled it before, so a single slot — not a pool — matches the existing
intent rather than fighting it. A second submission while one is active returns 409.

Streaming uses asyncio subprocesses (works on Windows' Proactor loop that uvicorn runs,
and on POSIX). Each run keeps a full in-memory log so a browser that connects late (or
reconnects) still receives everything from the top, then live lines, then an exit frame.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

HISTORY_PATH = Path(__file__).resolve().parent / "run_history.jsonl"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunBusy(Exception):
    """Raised when a run is requested while another is active (maps to HTTP 409)."""


class Run:
    """A single scripted subprocess run and everything a subscriber needs to follow it."""

    def __init__(self, model: str, action: str, argv: list[str]):
        self.id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:6]
        self.model = model
        self.action = action
        self.argv = argv
        self.status = "queued"  # queued | running | finished | cancelled | error
        self.exit_code: int | None = None
        self.start: str | None = None
        self.end: str | None = None
        self.lines: list[str] = []
        self._subscribers: set[asyncio.Queue] = set()
        self._proc: asyncio.subprocess.Process | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.id,
            "model": self.model,
            "action": self.action,
            "argv": self.argv,
            "status": self.status,
            "exit_code": self.exit_code,
            "start": self.start,
            "end": self.end,
        }

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _broadcast(self, frame: dict) -> None:
        for q in list(self._subscribers):
            q.put_nowait(frame)

    def _emit(self, line: str) -> None:
        self.lines.append(line)
        self._broadcast({"type": "stdout", "line": line})


class RunManager:
    def __init__(self, env: dict[str, str], cwd: Path):
        self._env = env
        self._cwd = cwd
        self._current: Run | None = None
        self._runs: dict[str, Run] = {}
        self._lock = asyncio.Lock()

    @property
    def current(self) -> Run | None:
        return self._current

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    async def start(self, model: str, action: str, argv: list[str]) -> Run:
        async with self._lock:
            if self._current is not None and self._current.status in {"queued", "running"}:
                raise RunBusy()
            run = Run(model, action, argv)
            self._runs[run.id] = run
            self._current = run
        await self._spawn(run)
        return run

    async def _spawn(self, run: Run) -> None:
        creationflags = 0
        preexec_fn = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # enables CTRL_BREAK
        else:
            preexec_fn = os.setsid  # new session so we can killpg the whole tree

        run.start = _now()
        run.status = "running"
        run._proc = await asyncio.create_subprocess_exec(
            *run.argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(self._cwd),
            env=self._env,
            creationflags=creationflags,
            preexec_fn=preexec_fn,
        )
        asyncio.create_task(self._pump(run))

    async def _pump(self, run: Run) -> None:
        assert run._proc is not None
        try:
            stdout = run._proc.stdout
            assert stdout is not None
            while True:
                raw = await stdout.readline()
                if not raw:
                    break
                run._emit(raw.decode("utf-8", errors="replace").rstrip("\n"))
            code = await run._proc.wait()
        except Exception as exc:  # pragma: no cover - defensive
            run._emit(f"[console] stream error: {exc!r}")
            code = -1

        run.exit_code = code
        run.end = _now()
        if run.status != "cancelled":
            run.status = "finished" if code == 0 else "error"
        run._broadcast({"type": "exit", "code": code, "status": run.status})
        self._append_history(run)
        if self._current is run:
            self._current = None

    async def cancel(self, run: Run) -> bool:
        if run._proc is None or run._proc.returncode is not None:
            return False
        run.status = "cancelled"
        run._emit("[console] cancel requested — terminating process group…")
        try:
            if os.name == "nt":
                run._proc.send_signal(signal.CTRL_BREAK_EVENT)
                # Give it a moment; hard-kill if it ignores CTRL_BREAK.
                await asyncio.sleep(1.5)
                if run._proc.returncode is None:
                    run._proc.kill()
            else:
                os.killpg(os.getpgid(run._proc.pid), signal.SIGTERM)
                await asyncio.sleep(1.5)
                if run._proc.returncode is None:
                    os.killpg(os.getpgid(run._proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as exc:  # pragma: no cover
            run._emit(f"[console] cancel error: {exc!r}")
        return True

    def _append_history(self, run: Run) -> None:
        try:
            with HISTORY_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(run.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass  # history is best-effort; never break a run over it

    def history(self, limit: int = 100) -> list[dict]:
        rows: list[dict] = []
        if HISTORY_PATH.exists():
            for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        rows.reverse()  # newest first
        return rows[:limit]
