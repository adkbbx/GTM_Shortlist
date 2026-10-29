"""The public agent demo (shortlist.agent.public) with LABELLED SYNTHETIC providers, for browser tests on port 8017.

Never use this as the live demo: it researches invented .example companies only and spends nothing.
"""
import secrets
import tempfile
from pathlib import Path

import uvicorn

from shortlist.agent.public import PublicSettings, create_public_app
from shortlist.agent.settings import AgentSettings

data = tempfile.TemporaryDirectory(prefix="gtm-shortlist-public-")
settings = PublicSettings(app_url="http://127.0.0.1:8017", secret=secrets.token_hex(32), data_dir=Path(data.name),
                          synthetic=True, runs_per_hour=50, max_active=10)
application = create_public_app(settings, agent_settings=lambda: AgentSettings())

if __name__ == "__main__":
    try:
        uvicorn.run(application, host="127.0.0.1", port=8017, log_level="warning")
    finally:
        data.cleanup()
