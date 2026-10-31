"""Key-free research commands. Run `python -m agent.cli --help`."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .research_rules import json_safe, require_bayesian_inputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Exploratory research tools; no sensitive data.")
    commands = parser.add_subparsers(dest="command", required=True)
    caveat_parser = commands.add_parser("caveat", help="Inspect a CSV result table")
    caveat_parser.add_argument("--csv", required=True)
    caveat_parser.add_argument("--question", default="")
    assurance_parser = commands.add_parser("assurance", help="Calculate a Bayesian design from JSON")
    assurance_parser.add_argument("--json", required=True)
    analyze_parser = commands.add_parser("analyze", help="Run an approved analysis specification")
    analyze_parser.add_argument("--spec", required=True)
    analyze_parser.add_argument("--csv", required=True)
    analyze_parser.add_argument("--confirm", action="store_true", help="Confirm the specification was reviewed")
    args = parser.parse_args(argv)
    try:
        if args.command == "caveat":
            import caveat
            import pandas as pd
            result = caveat.analyze(pd.read_csv(args.csv), question=args.question).as_dict()
        elif args.command == "assurance":
            import assurance
            params = json.loads(Path(args.json).read_text())
            require_bayesian_inputs(params)
            result = asdict(assurance.design(**params))
        else:
            import pandas as pd

            from . import research
            spec = json.loads(Path(args.spec).read_text())
            if Path(spec.get("data_source", "")).resolve() != Path(args.csv).resolve():
                raise ValueError("The specified data source does not match the --csv file.")
            frame = pd.read_csv(args.csv)
            model = research.run_spec(spec, frame, approved=args.confirm, source_identity=spec["data_source"])
            if model.error:
                raise ValueError(model.error)
            result = research.make_bundle(spec, model.as_dict(), frame=frame)
        print(json.dumps(json_safe(result), indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
