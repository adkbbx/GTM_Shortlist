import csv
import io

import pytest

from shortlist.export import export_run


@pytest.mark.parametrize("name", ["=HYPERLINK(\"evil\")", "+1+1", "-1+1", "@SUM(A1:A2)", "\t=1+1", "\r=1+1"])
def test_csv_formula_cells_are_escaped(name):
    run = {"id": "run", "profile": {}, "status": "partial", "checkpoint": {}, "records": [{
        "research": {"name": name, "domain": "example.com", "qualification": "needs_verification",
                     "status": "partial", "findings": [], "sources": [], "hypotheses": [], "unknowns": []},
        "review": None}]}
    rows = list(csv.reader(io.StringIO(export_run(run, "csv"))))
    assert rows[1][0].startswith("'")
