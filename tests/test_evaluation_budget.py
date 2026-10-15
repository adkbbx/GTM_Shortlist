"""Development evaluations must stop before reading credentials or creating state."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("script", ["evaluate_market.py", "evaluate_semantics.py", "evaluate_shortlist.py", "evaluate_seller.py"])
def test_live_evaluation_requires_explicit_opt_in(tmp_path, script):
    repository = Path(__file__).resolve().parents[1]
    output = tmp_path / "evaluation.sqlite3"
    args = [sys.executable, str(repository / "scripts" / script)]
    if script in ("evaluate_market.py", "evaluate_shortlist.py"):
        args += ["--source-db", str(tmp_path / "missing-source.sqlite3"),
                 "--source-run", "missing", "--output-db", str(output),
                 "--provider-env", str(tmp_path / "missing-secrets.env")]
    elif script == "evaluate_seller.py":
        args += ["--source-json", str(tmp_path / "missing-source.json"), "--output-db", str(output),
                 "--provider-env", str(tmp_path / "missing-secrets.env")]
    else:
        args += ["--cases", str(tmp_path / "missing-cases.json"), "--database", str(output)]
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 2
    assert "Live evaluation is disabled" in result.stderr
    assert "--allow-provider-calls" in result.stderr
    assert not list(tmp_path.iterdir())
