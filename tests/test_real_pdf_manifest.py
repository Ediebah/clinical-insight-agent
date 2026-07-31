"""Integrity checks for the public-PDF regression cohort.

The publications are not committed. The manifest pins public sources and the
exact files used for manual/live validation without redistributing the PDFs.
"""

import json
import re
from pathlib import Path


def test_public_pdf_regression_manifest_is_pinned_and_keeps_identity_case():
    path = Path(__file__).parent / "fixtures" / "published_pdf_validation.json"
    sources = json.loads(path.read_text())

    assert 5 <= len(sources) <= 10
    assert len({source["id"] for source in sources}) == len(sources)
    assert len({source["url"] for source in sources}) == len(sources)
    assert all(re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) for source in sources)
    assert all(source["title"] and source["url"].startswith("https://") for source in sources)

    lee_liu = next(source for source in sources if source["id"] == "lee-liu-2008")
    assert lee_liu["doi"] == "10.1177/1740774508089279"
    assert "predictive probability design" in lee_liu["title"].casefold()
    assert all(source.get("doi") != "10.1002/sim.3021" for source in [lee_liu])
