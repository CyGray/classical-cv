"""LS-Face Local Run Console — FastAPI app (localhost-only).

Wraps main.py's ~38 menu actions in a browser tab: a Terminal tab that IS main.py's own
interactive loop, and a Forms tab that shells out to the same scripts with the same argv
run_choice would build. Binds 127.0.0.1 ONLY — never reachable off the machine
(DESIGN.md §5.5). Single job at a time (DESIGN.md §5.3).

Run:  python -m uvicorn ui.console.app:app --port 8756
  or: python ui/console/app.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
# Put this dir on sys.path so the sibling modules import the same whether the app is
# started as `python -m uvicorn ui.console.app:app` (from repo root) or `python -m
# ui.console` — no dependency on relative-import package context.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import action_registry as reg  # noqa: E402
import form_fields as ff  # noqa: E402
from run_manager import RunBusy, RunManager  # noqa: E402
BIND_HOST = "127.0.0.1"  # literal, not env-configurable by default (DESIGN.md §5.5)
BIND_PORT = 8756

app = FastAPI(title="LS-Face Run Console", docs_url="/api/docs")
templates = Jinja2Templates(directory=str(HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

manager = RunManager(env=reg.subprocess_env(), cwd=PROJECT_ROOT)


@app.on_event("startup")
async def _startup() -> None:
    # Fail loudly if form_fields drifted from GROUPED_CHOICES (BUILD.md 3.1 assertion).
    orphans = ff.selfcheck(reg.action_pairs())
    if orphans:
        raise RuntimeError(f"form_fields has actions not in GROUPED_CHOICES: {orphans}")


# ---- Pages -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "groups": reg.list_groups(), "active": "home"},
    )


@app.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request):
    return templates.TemplateResponse(
        "terminal.html", {"request": request, "active": "terminal"}
    )


@app.get("/forms", response_class=HTMLResponse)
async def forms_page(request: Request):
    # Only expose actions that actually have a form spec.
    groups = []
    for g in reg.list_groups():
        actions = [a for a in g["actions"] if ff.has_form(g["model"], a["label"])]
        if actions:
            groups.append({"model": g["model"], "actions": actions})
    return templates.TemplateResponse(
        "forms.html", {"request": request, "groups": groups, "active": "forms"}
    )


# ---- API: actions & forms ----------------------------------------------------
@app.get("/api/actions")
async def api_actions():
    return {"groups": reg.list_groups()}


@app.get("/api/actions/form-fields")
async def api_form_fields(model: str, action: str):
    fields = ff.form_for(model, action)
    if fields is None:
        return JSONResponse({"error": "no form for this action"}, status_code=404)
    return {"model": model, "action": action, "fields": fields}


@app.get("/api/models/trained")
async def api_models_trained():
    """Scan models/<family>/*.{yml,onnx} + labels_*.json (DESIGN.md §5.6)."""
    families = {
        "LBPH": "lbph",
        "Eigenfaces": "eigenfaces",
        "Fisherfaces": "fisherfaces",
        "Hybrid": "sface",
    }
    out: dict[str, list[dict]] = {}
    for family, subdir in families.items():
        d = PROJECT_ROOT / "models" / subdir
        rows: list[dict] = []
        if d.is_dir():
            for pat in ("*.yml", "*.onnx", "*.npy"):
                for p in sorted(d.glob(pat)):
                    st = p.stat()
                    rows.append(
                        {
                            "path": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                            "exists": True,
                            "size_bytes": st.st_size,
                        }
                    )
        out[family] = rows
    return out


# ---- API: runs ---------------------------------------------------------------
@app.post("/api/runs")
async def api_start_run(payload: dict):
    model = payload.get("model", "")
    action = payload.get("action", "")
    values = payload.get("values", {}) or {}
    extra = (payload.get("extra_args") or "").strip()

    if not ff.has_form(model, action):
        return JSONResponse({"error": "unknown or non-form action"}, status_code=400)

    import shlex

    args = ff.build_args(model, action, values)
    if extra:
        args += shlex.split(extra)

    argv = reg.build_command(model, action, args)
    if argv is None:
        return JSONResponse({"error": "could not resolve script"}, status_code=400)

    # Pre-flight the same missing-artifact check the menu does for evaluate actions.
    warnings: list[str] = []
    if ff.is_evaluation_action(action):
        missing = reg.check_missing_artifacts(args, is_evaluation=True)
        if missing:
            warnings = [f"Missing artifact: {m}" for m in missing]

    try:
        run = await manager.start(model, action, argv)
    except RunBusy:
        return JSONResponse(
            {"error": "a run is already in progress", "current": manager.current.to_dict() if manager.current else None},
            status_code=409,
        )
    return {"run_id": run.id, "status": run.status, "argv": argv, "warnings": warnings}


@app.post("/api/runs/{run_id}/cancel")
async def api_cancel_run(run_id: str):
    run = manager.get(run_id)
    if run is None:
        return JSONResponse({"error": "unknown run"}, status_code=404)
    ok = await manager.cancel(run)
    if not ok:
        return JSONResponse({"error": "run already finished"}, status_code=409)
    return {"status": "cancelling"}


@app.get("/api/runs")
async def api_run_history():
    return manager.history()


@app.get("/api/runs/{run_id}")
async def api_run_detail(run_id: str):
    run = manager.get(run_id)
    if run is None:
        # fall back to history for finished-but-evicted runs
        for row in manager.history(limit=1000):
            if row.get("run_id") == run_id:
                return row
        return JSONResponse({"error": "unknown run"}, status_code=404)
    return {**run.to_dict(), "log": run.lines}


@app.websocket("/api/runs/{run_id}/stream")
async def ws_run_stream(ws: WebSocket, run_id: str):
    await ws.accept()
    run = manager.get(run_id)
    if run is None:
        await ws.send_json({"type": "error", "message": "unknown run"})
        await ws.close()
        return
    # Replay the buffered log first so a late subscriber sees everything.
    for line in list(run.lines):
        await ws.send_json({"type": "stdout", "line": line})
    if run.status in {"finished", "error", "cancelled"}:
        await ws.send_json({"type": "exit", "code": run.exit_code, "status": run.status})
        await ws.close()
        return

    q = run.subscribe()
    try:
        while True:
            frame = await q.get()
            await ws.send_json(frame)
            if frame.get("type") == "exit":
                break
    except WebSocketDisconnect:
        pass
    finally:
        run.unsubscribe(q)
    with contextlib.suppress(Exception):
        await ws.close()


# ---- WebSocket: Terminal relay (interactive main.py) -------------------------
@app.websocket("/api/terminal")
async def ws_terminal(ws: WebSocket):
    await ws.accept()
    import os
    import subprocess

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = await asyncio.create_subprocess_exec(
        *reg.main_py_command(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        env=reg.subprocess_env(),
        creationflags=creationflags,
    )

    async def pump_stdout():
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            with contextlib.suppress(Exception):
                await ws.send_json(
                    {"type": "stdout", "line": raw.decode("utf-8", errors="replace").rstrip("\n")}
                )
        with contextlib.suppress(Exception):
            code = await proc.wait()
            await ws.send_json({"type": "exit", "code": code})

    out_task = asyncio.create_task(pump_stdout())
    try:
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
                line = data.get("input", "")
            except json.JSONDecodeError:
                line = msg
            if proc.stdin is not None and proc.returncode is None:
                proc.stdin.write((line + "\n").encode("utf-8"))
                with contextlib.suppress(Exception):
                    await proc.stdin.drain()
    except WebSocketDisconnect:
        pass
    finally:
        out_task.cancel()
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                if os.name == "nt":
                    proc.kill()
                else:
                    proc.terminate()
        with contextlib.suppress(Exception):
            await ws.close()


# ---- Health ------------------------------------------------------------------
@app.get("/api/health")
async def api_health():
    return {"status": "ok", "bound_host": BIND_HOST}


if __name__ == "__main__":
    import uvicorn

    print(f"[console] LS-Face Run Console on http://{BIND_HOST}:{BIND_PORT} (localhost only)")
    uvicorn.run(app, host=BIND_HOST, port=BIND_PORT)
