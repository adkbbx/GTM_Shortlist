"""Serve the built landing page with an isolated local API and no research providers.

Run from the repository root. This is a local UI preview, not a hosted deployment.
The normal app server remains the entry point for configured real research.
"""
import argparse
import tempfile
from pathlib import Path

import uvicorn

from shortlist.api import create_app
from shortlist.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8018)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="shortlist-landing-preview-") as directory:
        app = create_app(Settings(db_path=Path(directory) / "preview.sqlite3"))
        print("Local UI preview: isolated data, no configured providers, no worker.", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
