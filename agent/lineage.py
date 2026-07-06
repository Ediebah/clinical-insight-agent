"""Data lineage / provenance — answers "where did this number come from?" by walking the dbt DAG.

The lineage (each table's transitive upstream, back to raw Synthea sources) is baked into the
semantic catalog at build time by build_catalog.py, so this module needs no manifest at runtime and
works on the deployed app. Two jobs:
  1. detect + answer a lineage question ("where does the readmission rate come from?") deterministically.
  2. attach a provenance trace to every analysis (the lineage of the tables its SQL touched).

This is the "map lineage to answer where a data point originated" capability — from the dbt graph,
not manual debugging.
"""
from __future__ import annotations

import re

# Upstream layers, ordered raw → … → analytics (the order build_catalog.py emits them in).
_LAYERS_UP = ["core", "staging", "raw"]              # for a mart, the chain reads mart ← core ← staging ← raw
_INTENT = re.compile(
    r"\b(where\s+(?:does|do|did|is|are)\b[^?]*\b(?:come|comes|coming|came|originate|originated|"
    r"derived?|sourced?|from)\b|lineage|provenance|upstream|downstream|data\s+source|source\s+table|"
    r"how\s+(?:is|are|was|were)\b[^?]*\b(?:built|computed|calculated|derived|generated|produced|populated)\b|"
    r"what\s+(?:feeds|builds|produces|goes\s+into|makes\s+up|is\s+behind|powers)\b|"
    r"trace\b[^?]*\b(?:back|origin|source|lineage)\b|"
    r"what\s+(?:uses|depends\s+on|consumes|breaks|is\s+downstream|would\s+break))\b", re.I)
_DOWNSTREAM = re.compile(
    r"\b(downstream|what\s+(?:uses|depends\s+on|consumes|breaks|reads)|impact|breaks?\s+if|"
    r"what\s+is\s+downstream)\b", re.I)


def _by_name(catalog: dict) -> dict:
    return {t["name"]: t for t in catalog.get("tables", [])}


def _phrase_map(catalog: dict) -> list[tuple[str, str]]:
    """(phrase, table_name) pairs, longest phrase first, so a question can name a table/metric loosely
    ('readmissions', 'the readmission rate', 'patient data'). Includes singular/plural + suffix-stripped
    metric forms so 'readmission rate' resolves 'readmission_rate_30d' → mart_readmissions."""
    pairs: dict[str, str] = {}

    def add(phrase: str, table: str) -> None:
        phrase = phrase.lower().strip()
        if phrase:
            pairs[phrase] = table

    for t in catalog.get("tables", []):
        n = t["name"]
        bare = re.sub(r"^(mart|dim|fct|stg)_", "", n)
        forms = {n, bare}
        forms.add(bare[:-1] if bare.endswith("s") else bare + "s")   # singular ↔ plural
        for f in list(forms):
            add(f, n)
            add(f.replace("_", " "), n)
    for m in catalog.get("metrics", []):
        model = m.get("model")
        if not model:
            continue
        nm = m["name"]
        stripped = re.sub(r"_\d+d?$", "", nm)                        # readmission_rate_30d → readmission_rate
        for f in {nm, stripped}:
            add(f, model)
            add(f.replace("_", " "), model)
    return sorted(pairs.items(), key=lambda kv: -len(kv[0]))


def detect(question: str, catalog: dict | None) -> str | None:
    """If `question` asks about lineage AND names a known table/metric, return that table name."""
    if not catalog or not _INTENT.search(question or ""):
        return None
    ql = f" {question.lower()} "
    for phrase, table in _phrase_map(catalog):
        if len(phrase) < 4:                              # skip ultra-short, ambiguous keys
            continue
        if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", ql):
            return table
    return None


def is_downstream(question: str) -> bool:
    return bool(_DOWNSTREAM.search(question or ""))


def _chain(entry: dict) -> str:
    """A backward provenance chain: `mart_x ← [core] a ← [staging] b ← [raw] src` (its own layer skipped)."""
    by_layer: dict[str, list[str]] = {}
    for d in entry.get("upstream", []):
        by_layer.setdefault(d["layer"], []).append(d["name"])
    parts = [f"**{entry['name']}**"]
    for layer in _LAYERS_UP:
        names = by_layer.get(layer)
        if names and layer != entry.get("layer"):
            parts.append(f"[{layer}] " + ", ".join(sorted(set(names))))
    return " ← ".join(parts)


def downstream_of(table: str, catalog: dict) -> list[str]:
    """Tables in the catalog whose lineage includes `table` — i.e. what would be affected if it breaks."""
    out = []
    for t in catalog.get("tables", []):
        if t["name"] == table:
            continue
        ups = {d["name"] for d in t.get("upstream", [])} | set(t.get("depends_on", []))
        if table in ups:
            out.append(t["name"])
    return sorted(out)


def provenance(table: str, catalog: dict) -> dict | None:
    """Structured provenance for one table: direct inputs, full upstream, raw sources, downstream."""
    entry = _by_name(catalog).get(table)
    if entry is None:
        return None
    up = entry.get("upstream", [])
    return {
        "table": table,
        "depends_on": entry.get("depends_on", []),
        "sources": [d["name"] for d in up if d["layer"] == "raw"],
        "upstream": up,
        "downstream": downstream_of(table, catalog),
        "chain": _chain(entry),
    }


def answer(table: str, catalog: dict, downstream: bool = False) -> str:
    """A deterministic, human-readable lineage answer for a lineage question (no LLM)."""
    p = provenance(table, catalog)
    if not p:
        return f"`{table}` isn't a modeled table in this warehouse, so I can't trace its lineage."
    if downstream:
        deps = p["downstream"]
        body = ("\n".join(f"- `{d}`" for d in deps) if deps
                else "_Nothing downstream — no other modeled table depends on it._")
        return (f"**What depends on `{table}`** (would be affected if it changes/breaks):\n\n{body}\n\n"
                f"Direct inputs to `{table}`: {', '.join(f'`{d}`' for d in p['depends_on']) or '—'}.")
    if not p["upstream"] and not p["depends_on"]:
        down = ", ".join(f"`{d}`" for d in p["downstream"]) or "—"
        return (f"**`{table}` has no upstream lineage** — it is generated within its own model "
                f"(no raw source or parent table; e.g. synthetic data via `generate_series`), so there "
                f"is nothing further to trace back to. Downstream (what reads it): {down}.")
    srcs = ", ".join(f"`{s}`" for s in p["sources"]) or "—"
    deps = ", ".join(f"`{d}`" for d in p["depends_on"]) or "—"
    return (f"**Where `{table}` comes from** (traced through the dbt lineage, not by manual debugging):\n\n"
            f"{p['chain']}\n\n"
            f"- **Raw source(s):** {srcs}\n"
            f"- **Direct inputs (immediate parents):** {deps}\n"
            f"- **Downstream (what reads it):** "
            f"{', '.join(f'`{d}`' for d in p['downstream']) or '—'}")


def for_tables(table_names: list[str], catalog: dict | None) -> dict | None:
    """Provenance trace to attach to an analysis result — the lineage of the tables its SQL touched.
    Returns None (no-op) for BYOD / when nothing resolves, so callers can gate on truthiness."""
    if not catalog:
        return None
    entries, sources = [], []
    for name in dict.fromkeys(table_names or []):        # dedup, keep order
        p = provenance(name, catalog)
        if p:
            entries.append({"name": name, "chain": p["chain"], "depends_on": p["depends_on"]})
            sources.extend(p["sources"])
    if not entries:
        return None
    return {"tables": entries, "sources": sorted(set(sources))}
