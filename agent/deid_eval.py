"""Measure the de-identification model against identifiers Synthea already knows.

`agent/deid.py` reduces exposure by an amount nobody has measured: OpenMed publishes no recall
figures for the model. This harness supplies the missing number, using Synthea's own generated
identifiers as labels — no annotation, and no data-use agreement, which matters because the
standard corpora (i2b2/n2c2) are access-controlled.

Run:  .venv/bin/python -m agent.deid_eval

NOT run in CI: the model is a 453 MB download. CI unit-tests this harness against a mock, in the
same way route_eval and bayes_eval sit outside CI while guardrail_eval runs inside it.

Two corpus variants are scored. Synthea marks its output as fake — names carry numeric suffixes,
ZIP is 00000, SSNs use the reserved 999 prefix — so a figure measured on the raw form describes
Synthea rather than clinical text. The normalised variant is the headline; the gap between the two
measures how much those markers distort the result.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from . import deid

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "healthcare.duckdb"
HISTORY = Path(__file__).resolve().parent / "deid_eval_history.jsonl"

_SUFFIX = re.compile(r"\d+$")


@dataclass(frozen=True)
class Identity:
    """One patient's identifiers, as ground truth."""
    first: str
    last: str
    ssn: str
    address: str
    city: str
    zip: str
    mrn: str
    birthdate: str


def _stable_digits(seed: str, n: int) -> str:
    """Deterministic digits from a seed — a benchmark that moves between runs is useless."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    return "".join(str(int(c, 16) % 10) for c in h[:n])


def _mrn(patient_id: str) -> str:
    return f"MRN {_stable_digits(patient_id, 6)}"


def raw_identities(rows: list[dict]) -> list[Identity]:
    """Exactly what Synthea emits, markers and all."""
    return [Identity(
        first=r["FIRST"], last=r["LAST"], ssn=r["SSN"], address=r["ADDRESS"],
        city=r["CITY"], zip=r["ZIP"], mrn=_mrn(r["Id"]), birthdate=r["BIRTHDATE"],
    ) for r in rows]


def normalise(rows: list[dict]) -> list[Identity]:
    """Strip Synthea's synthetic markers so the corpus reads like clinical text.

    Names lose their trailing digits (Brekke496 -> Brekke); the 00000 ZIP and the reserved
    999-prefix SSN are replaced with format-valid fakes derived deterministically from the
    patient id. This does NOT make the distribution real — see the spec's open risks — it only
    removes markers that would make the model's job artificially different.
    """
    out = []
    for r in rows:
        pid = r["Id"]
        out.append(Identity(
            first=_SUFFIX.sub("", r["FIRST"]),
            last=_SUFFIX.sub("", r["LAST"]),
            ssn=f"{_stable_digits(pid + 'a', 3)}-{_stable_digits(pid + 'b', 2)}-"
                f"{_stable_digits(pid + 'c', 4)}",
            address=r["ADDRESS"],
            city=r["CITY"],
            zip=_stable_digits(pid + "z", 5),
            mrn=_mrn(pid),
            birthdate=r["BIRTHDATE"],
        ))
    return out


def load_rows(db_path: str | Path = DB_PATH, limit: int = 200) -> list[dict]:
    """Read raw.patients, or exit with the rebuild instruction.

    raw.patients exists only in the FULL local warehouse. The committed demo database ships the
    modelled tables only, and dim_patient deliberately carries no name, SSN or address.
    """
    cols = ["Id", "FIRST", "LAST", "SSN", "ADDRESS", "CITY", "ZIP", "BIRTHDATE"]
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Cannot open {db_path}: {exc}\nBuild it first: python scripts/load_raw.py")
    limit_int = int(limit)
    try:
        rows = con.execute(
            f"select {', '.join(cols)} from raw.patients limit {limit_int}").fetchall()
    except Exception:  # noqa: BLE001
        raise SystemExit(
            f"raw.patients not found in {db_path}.\n"
            "This benchmark needs the FULL warehouse, not the slim demo database. Generate the "
            "Synthea data, then run: python scripts/load_raw.py")
    finally:
        con.close()
    return [dict(zip(cols, r)) for r in rows]


# Columns holding real identifiers, and columns that must NOT be flagged. A clean column flagged
# is a false positive that costs the user an unnecessary decision.
IDENTIFIER_COLUMNS = {"first", "last", "ssn", "address", "zip", "mrn", "birthdate"}
CLEAN_COLUMNS = ("systolic_bp", "cured", "encounter_count", "cost_usd")


def build_frame(identities: list[Identity]) -> tuple[pd.DataFrame, set[str]]:
    """A frame with known identifier columns, known-clean columns, and the two quasi covariates."""
    n = len(identities)
    df = pd.DataFrame({
        "first": [i.first for i in identities],
        "last": [i.last for i in identities],
        "ssn": [i.ssn for i in identities],
        "address": [i.address for i in identities],
        "zip": [i.zip for i in identities],
        "mrn": [i.mrn for i in identities],
        "birthdate": [i.birthdate for i in identities],
        # quasi covariates — must survive as `quasi`, not be suggested for dropping
        "age": [40 + (k % 45) for k in range(n)],
        "sex": ["M" if k % 2 else "F" for k in range(n)],
        # known-clean
        "systolic_bp": [110 + (k % 40) for k in range(n)],
        "cured": [k % 2 for k in range(n)],
        "encounter_count": [1 + (k % 9) for k in range(n)],
        "cost_usd": [100.0 + k for k in range(n)],
    })
    return df, set(IDENTIFIER_COLUMNS)


def score_columns(df: pd.DataFrame, truth: set[str]) -> dict:
    """Precision and recall over COLUMNS, plus the quasi-severity check."""
    findings = deid.scan_columns(df)
    flagged = {f.column for f in findings}
    hits = flagged & truth
    missed = truth - flagged
    false_positives = {c for c in flagged - truth if c in CLEAN_COLUMNS}
    # age and sex are expected to be flagged, but as `quasi` suggesting keep — never dropped.
    quasi_ok = all(f.severity == "quasi" and f.suggested == "keep"
                   for f in findings if f.column in ("age", "sex"))
    return {
        "recall": len(hits) / len(truth) if truth else 1.0,
        "precision": len(hits) / len(flagged) if flagged else 1.0,
        "flagged": sorted(flagged),
        "missed": sorted(missed),
        "false_positives": sorted(false_positives),
        "quasi_ok": quasi_ok,
    }


_NOTE = ("Patient {name} (MRN {mrn_digits}), DOB {date}, SSN {ssn}, resides at {address}, "
         "{city} {zip}. Seen today in clinic; vitals stable and follow-up arranged.")

ENTITY_TYPES = ("name", "ssn", "address", "zip", "mrn", "date")


def build_notes(identities: list[Identity]) -> list[tuple[str, dict[str, str]]]:
    """Note-like text with known identifiers embedded, paired with what was inserted.

    Templated, not real: ground truth requires knowing exactly what went in. Real clinical text is
    messier and would very likely score worse — see the spec's open risks.
    """
    out = []
    for i in identities:
        name = f"{i.first} {i.last}"
        mrn_digits = i.mrn.replace("MRN ", "")
        text = _NOTE.format(name=name, mrn_digits=mrn_digits, date=i.birthdate, ssn=i.ssn,
                            address=i.address, city=i.city, zip=i.zip)
        out.append((text, {"name": name, "ssn": i.ssn, "address": i.address,
                           "zip": i.zip, "mrn": mrn_digits, "date": i.birthdate}))
    return out


def score_spans(notes: list[tuple[str, dict[str, str]]]) -> dict:
    """Per-entity-type recall: the share of inserted values no longer present after scrubbing."""
    scrubbed = deid.scrub_values([t for t, _ in notes])
    found = {k: 0 for k in ENTITY_TYPES}
    total = {k: 0 for k in ENTITY_TYPES}
    leaks: dict[str, list[str]] = {k: [] for k in ENTITY_TYPES}
    for out_text, (_orig, truth) in zip(scrubbed, notes):
        for kind, value in truth.items():
            total[kind] += 1
            if value not in out_text:
                found[kind] += 1
            elif len(leaks[kind]) < 5:      # evidence, capped so output stays readable
                leaks[kind].append(value)
    recall = {k: (found[k] / total[k] if total[k] else 1.0) for k in ENTITY_TYPES}
    all_found, all_total = sum(found.values()), sum(total.values())
    return {"recall": recall,
            "overall": all_found / all_total if all_total else 1.0,
            "leaks": leaks}
