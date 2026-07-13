"""`python -m ui.console` — start the local run console on 127.0.0.1:8756."""

from __future__ import annotations

import uvicorn

from .app import BIND_HOST, BIND_PORT, app

if __name__ == "__main__":
    print(f"[console] LS-Face Run Console on http://{BIND_HOST}:{BIND_PORT} (localhost only)")
    uvicorn.run(app, host=BIND_HOST, port=BIND_PORT)
