"""Copy the built UI into the Python package before a release build, so `uvx gtm-shortlist` needs no Node.

Run `npm ci && npm run build` first. Then `python scripts/package_ui.py` and `python -m build --outdir package-dist`
(the default dist/ folder belongs to the UI build).
"""
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
built, packaged = root / "dist", root / "src" / "shortlist" / "web_dist"
if not (built / "index.html").is_file():
    sys.exit("No built UI in dist/. Run npm ci and npm run build first.")
shutil.rmtree(packaged, ignore_errors=True)
shutil.copytree(built, packaged)
files = sum(1 for path in packaged.rglob("*") if path.is_file())
print(f"Packaged {files} UI files into {packaged.relative_to(root)}")
