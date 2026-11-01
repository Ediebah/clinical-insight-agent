"""Record package-declared license metadata, not a legal or provenance audit."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path


def inventory(requirements: Path) -> dict:
    distributions = []
    for dist in importlib.metadata.distributions():
        metadata = dist.metadata
        text = metadata.get("License")
        short_license = text if text and len(text) <= 240 and "\n" not in text else None
        distributions.append({
            "name": metadata["Name"], "version": dist.version,
            "license_expression": metadata.get("License-Expression"),
            "license_metadata": short_license,
            "license_metadata_omitted": bool(text and short_license is None),
            "license_classifiers": [c for c in metadata.get_all("Classifier", [])
                                    if c.startswith("License ::")],
            "license_files": metadata.get_all("License-File", []),
        })
    distributions.sort(key=lambda d: d["name"].lower())
    return {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "requirements_sha256": hashlib.sha256(requirements.read_bytes()).hexdigest(),
        "limitation": "Installed-package metadata only; not an exhaustive license review, "
                      "a distribution obligation assessment, or proof of provenance.",
        "distributions": distributions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, default=Path("requirements.txt"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(inventory(args.requirements), indent=2) + "\n")


if __name__ == "__main__":
    main()
