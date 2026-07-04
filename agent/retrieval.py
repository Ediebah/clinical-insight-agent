"""RAG over the semantic catalog.

The catalog is small (14 tables), so we use deterministic token-overlap scoring rather than
embeddings — no API call, instant, reproducible, and easy to unit-test. Given a question we
return the most relevant tables (with full column detail) plus any relevant named metrics, and
render them into a compact context block the LLM can ground its SQL on.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent / "semantic_catalog.json"

_STOP = {
    "the", "a", "an", "of", "for", "and", "or", "to", "in", "on", "by", "is", "are", "what",
    "which", "how", "many", "much", "do", "does", "did", "with", "per", "each", "that", "this",
    "show", "me", "give", "list", "find", "get", "average", "avg", "total", "number", "count",
}


def _stem(t: str) -> str:
    return t[:-1] if len(t) > 3 and t.endswith("s") else t   # crude plural strip: patients→patient


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9_]+", text.lower()) if t not in _STOP and len(t) > 1]


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return json.loads(path.read_text())


def _table_text(t: dict) -> str:
    """All searchable text for a table: name, description, and every column name+description."""
    cols = " ".join(f"{c['name']} {c['description']}" for c in t["columns"])
    return f"{t['name']} {t['description']} {cols}"


def _score(query_tokens: list[str], text: str) -> int:
    hay = set(_tokens(text))
    return sum(1 for q in query_tokens if q in hay)


def _clean_example(value, width: int = 40) -> str:
    """Render a catalog example value as inert DATA for the prompt: replace control chars (incl.
    newlines/tabs) with spaces, collapse whitespace, and hard-truncate — so an uploaded cell can't
    inject newlines or fake prompt structure into the rendered context."""
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))   # control chars → space (defang structure)
    s = re.sub(r"\s+", " ", s).strip()                 # collapse runs of whitespace
    return s[:width]


def retrieve(question: str, catalog: dict | None = None, k: int = 6) -> dict:
    """Return the top-k tables + relevant metrics for a question, plus a full table-name index."""
    catalog = load_catalog() if catalog is None else catalog   # an empty {} must NOT fall back to demo
    q = _tokens(question)

    scored_tables = sorted(
        ((_score(q, _table_text(t)), t) for t in catalog.get("tables", [])),
        key=lambda x: x[0], reverse=True,
    )
    # keep tables with any signal; fall back to the top-k if the question is vague
    hits = [t for s, t in scored_tables if s > 0][:k]
    if not hits:
        hits = [t for _, t in scored_tables[:k]]

    scored_metrics = sorted(
        ((_score(q, f"{m['name']} {m['definition']}"), m) for m in catalog.get("metrics", [])),
        key=lambda x: x[0], reverse=True,
    )
    metrics = [m for s, m in scored_metrics if s > 0][:4]

    return {
        "tables": hits,
        "metrics": metrics,
        "all_table_names": [t["name"] for t in catalog.get("tables", [])],
    }


def render_context(retrieved: dict) -> str:
    """Format retrieved tables + metrics into a compact grounding block for the LLM prompt."""
    lines: list[str] = []
    lines.append("AVAILABLE TABLES (query these; schema is `main`):")
    lines.append("  " + ", ".join(retrieved["all_table_names"]))
    lines.append("")
    lines.append("RELEVANT TABLE DETAIL:")
    for t in retrieved["tables"]:
        pk = ", ".join(t["primary_key"]) or "(none)"
        lines.append(f"\n• {t['name']}  —  {t['description']}")
        lines.append(f"  grain/PK: {pk}")
        if t["foreign_keys"]:
            fks = "; ".join(f"{f['column']}→{f['references_table']}.{f['references_column']}"
                            for f in t["foreign_keys"])
            lines.append(f"  joins: {fks}")
        col_strs = []
        for c in t["columns"]:
            s = f"{c['name']}({c['type']})"
            ex = c.get("example_values") or []
            if ex:
                s += " e.g. " + "|".join(_clean_example(e) for e in ex[:3])
            col_strs.append(s)
        lines.append("  columns: " + ", ".join(col_strs))
    if retrieved["metrics"]:
        lines.append("\nRELEVANT METRICS (use these definitions exactly):")
        for m in retrieved["metrics"]:
            lines.append(f"• {m['name']} = {m['sql']}  [{m['model']}] — {m['definition']}")
            lines.append(f"    caveat: {m['caveats']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    qn = " ".join(sys.argv[1:]) or "Which chronic conditions have the highest cost by age group?"
    r = retrieve(qn)
    print(f"Q: {qn}\n")
    print(render_context(r))
