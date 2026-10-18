# Contributing

Start with [AGENTS.md](AGENTS.md), [the implementation checklist](docs/IMPLEMENTATION.md) and [the handoff](docs/planning/IMPLEMENTATION_HANDOFF.md). Use the source setup in [README.md](README.md).

Keep changes small. Open an issue describing the problem or a pull request with the behavior changed and verification results. Use labelled fixtures for development. Never include keys, private databases, invented company claims or unlabelled sample evidence. Keep human review separate from model qualification.

Run backend checks from the repository root. In PowerShell:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe scripts/check_readme.py
```

On macOS or Linux, prefix Python commands with `PYTHONPATH=src` and use `.venv/bin/python`.

For UI changes, run `npm run build`, then `npm run test:ui`. Install Chromium with `npx playwright install chromium` first if needed. The suite uses labelled test servers and temporary databases. Inspect phone and laptop screenshots under `.impeccable/review/`, check horizontal overflow and keyboard use, and keep regression checks under `tests/ui`. Do not point fixture tests at a live database.

Development provider calls require specific prior approval, even if a script has an opt-in flag. Use saved evidence or fixtures by default. Update [PROGRESS.md](docs/PROGRESS.md) with actual checks and unfinished work. See [SECURITY.md](SECURITY.md) for vulnerability reports. Contributions use the repository's MIT licence.
