"""Serve the built landing page with an isolated local API and no research providers.

Run from the repository root. This is a local UI preview, not a hosted deployment.
The normal app server remains the entry point for configured real research.
"""
import argparse
import html
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from shortlist.api import create_app
from shortlist.config import Settings


def create_preview_app(database: Path, workspace_url: str = "http://127.0.0.1:8019/"):
    origin = urlsplit(workspace_url)
    if origin.scheme != "http" or origin.hostname not in ("127.0.0.1", "localhost") or origin.username or origin.password:
        raise ValueError("Preview handoff must point to the configured loopback research workspace")
    app = create_app(Settings(db_path=database))

    @app.middleware("http")
    async def preview_boundary(request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith("/api/") and not request.url.path.endswith("/stop"):
            return JSONResponse({"detail": "This is a design preview without a research worker. "
                                 "Open the research workspace to start a real run, or use Try the demo."}, status_code=409)
        if request.method == "GET" and request.url.path == "/":
            source = Path("dist/index.html").read_text(encoding="utf-8")
            marker = '<meta name="shortlist-preview-workspace" content="' + html.escape(workspace_url, quote=True) + '">'
            return HTMLResponse(source.replace("</head>", marker + "</head>"))
        return await call_next(request)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8018)
    parser.add_argument("--database", type=Path, help="Preserve an existing preview database across a server restart")
    parser.add_argument("--workspace-url", default="http://127.0.0.1:8019/")
    args = parser.parse_args()
    if args.database:
        uvicorn.run(create_preview_app(args.database, args.workspace_url), host="127.0.0.1", port=args.port, log_level="warning")
        return
    with tempfile.TemporaryDirectory(prefix="shortlist-landing-preview-") as directory:
        app = create_preview_app(Path(directory) / "preview.sqlite3", args.workspace_url)
        print("Local UI preview: isolated data, no configured providers, no worker.", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
