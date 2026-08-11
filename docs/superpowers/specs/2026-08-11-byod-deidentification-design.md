# On-device de-identification for the bring-your-own-data path — Design

**One-line:** Scan an uploaded table for identifiers with a local ONNX model, let the user decide per column what to drop, mask, or keep, and scrub every remaining path by which their data could reach the language model.

**Status:** design, architecture approved, awaiting spec review.

## 1. Motivation

The BYOD upload path carries this warning, in `app.py` and now on the About page:

> Uploads reach the server and the model sees your column names and query results, so use
> **synthetic or non-sensitive data only**.

That sentence is the ceiling on the whole project. Every claim it makes rests on "the data is
Synthea, so there is no PHI." A user with real clinical data cannot use the agent at all, and the
statistical machinery — the part that took the most work — is the part they cannot reach.

A local de-identification pass lifts part of that ceiling. It does not lift all of it, and §6 is
explicit about which part.

## 2. What OpenMed actually provides

Verified against the package and model card, not the launch post:

| | |
|---|---|
| Package | `openmed` 2.0.0 on PyPI, Apache-2.0, Python ≥3.10 (this project is 3.12) |
| Install | `pip install "openmed[hf]"`; ONNX Runtime is an extra |
| API | `extract_pii(text, model_name=...)`, `deidentify(text, method="mask"\|"replace")`, `OnnxModel.from_pretrained(...)` |
| Model | `OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android` — 44M-param DeBERTa-v2 |
| Runtime | INT8-quantized ONNX (`model_int8.onnx`), CPU by default |
| Coverage | 55+ identifier types, spanning all 18 HIPAA Safe Harbor categories |
| Distribution | Downloads from HF Hub on first use; loads from a local directory for air-gapped use |

**Two statements from OpenMed's own model card shape this design and are not footnotes:**

1. **No published accuracy or F1.** The card directs users to "evaluate recall, thresholds, and span
   behavior on appropriately governed data before deployment."
2. **"Local execution … does not by itself guarantee regulatory compliance."**

A de-identifier with unpublished recall cannot support a safety guarantee — one missed identifier is
a disclosure. Therefore this feature is designed as a **detector that informs a human decision**, not
as a gate that certifies data. §6 and §7 hold the line on what it is allowed to claim.

The launch post's headline figures (10M installs, 340M downloads) could not be verified; the
project's own year-in-review cites 29.7M Hugging Face downloads. Nothing in this design depends on
those numbers.

## 3. The exposure surface, measured

What can actually reach the language model from an upload, read out of the code rather than assumed:

| Exit | Size | Source |
|---|---|---|
| Column names | ≤60 | `userdata.MAX_COLS` |
| Example values in the catalog | ≤180 strings, each ≤28 chars | `build_catalog` — `[str(v)[:28] for v in pd.unique(s.dropna())[:3]]` |
| Query results | **≤30 rows** | `agent._preview_csv`, the only path frame content takes into a prompt |

The result-row figure is worth stating carefully, because the obvious number is wrong. A query
returns up to 1,000 rows (`warehouse.MAX_ROWS`) and the UI displays them, but only
`agent._preview_csv` ever renders frame content into a prompt, and its two callers cap it at 15 rows
(`_verify`) and 30 rows (`_interpret`). The model path does not widen this: `_interpret_model`
receives a `ModelResult` — terms, curve points, arms, fit statistics — which carries no raw cells,
so the 100,000-row analytic frame it fits on never reaches the model.

The uploaded frame itself is up to **200,000 rows × 60 columns = 12M cells** (`userdata.MAX_ROWS`).
Running a transformer NER over that on CPU inside a Streamlit session is not viable, and it is not
necessary: the frame is never sent anywhere. Only the three exits above cross the boundary.

This is why the design is structural first. A column removed from the frame before `prepare_upload`
never enters DuckDB, so it cannot appear in example values *or* in query results — one action closes
two exits.

## 4. Architecture

Three layers, each closing one exit.

### 4.1 `agent/deid.py` (new)

The only module that imports `openmed`. No Streamlit import, so it is testable headless — the same
boundary `about.py` uses.

```python
def available() -> bool
def scan_columns(df: pd.DataFrame, sample: int = 20) -> list[ColumnFinding]
def scrub_values(values: list[str]) -> list[str]
def scrub_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame
def apply_decisions(df: pd.DataFrame, drop: list[str], mask: list[str]) -> pd.DataFrame
```

`ColumnFinding` carries `column`, `entity_types`, `hit_rate` (fraction of the sample with a
detection), `examples` (**redacted** previews — the UI must never echo a detected identifier back to
the screen), and a `suggested` action per §4.4.

The model is loaded lazily on first call and cached at module level, so importing `deid` costs
nothing and a user who never uploads never downloads the model.

### 4.2 Structural layer — `app.py`, BYOD block

Between `read_upload` and `prepare_upload`: `scan_columns` on a sample, present findings, collect a
per-column decision, then `apply_decisions` on the frame. Dropped columns cease to exist before
DuckDB ever sees them.

### 4.3 Boundary layer — `userdata.build_catalog`

`scrub_values` over the ≤180 example values — *all* of them, not only the flagged ones. Dropped
columns are already gone and masked ones already carry no identifiers, so in practice this is a
second pass over columns the user chose to **keep**, plus columns the scan never flagged. Scrubbing
unflagged columns too costs nothing at this size and covers scan misses.

### 4.4 Policy layer — `run_analysis`

The upload produces a **de-id policy**: the list of columns the user was warned about and kept
unmasked — computed in the BYOD block as `{f.column for f in findings} - set(drop) - set(mask)`, and
stored in session state alongside the existing `byod` entry. `run_analysis` gains one optional
parameter, `deid_columns: list[str] | None = None`, threaded to **`_preview_csv`** — the single
choke point through which frame content reaches any prompt. Scrubbing there makes the guarantee
structurally true in one place rather than relying on every future call site remembering.

Bounded by construction: typically 0–2 columns × ≤30 rows, so a few dozen short strings per
question. This is small enough that the scrub is not a perceptible latency cost.

**The demo-warehouse path passes nothing and must be byte-for-byte unchanged** — no scrub, no
latency, no model load. §8 has a regression test asserting exactly that, because this is the one
place a privacy feature could degrade the main product.

### 4.5 Default actions

Derived from the sample, and stated so the user can disagree with the rule rather than guess at it:

| Hit rate | Default | Why |
|---|---|---|
| ≥ 0.8 | **Drop** | The column *is* identifiers. Masking leaves a useless column, and dropping is structurally certain rather than dependent on span recall. |
| < 0.8 | **Mask** | Identifiers appear inside other content (free-text notes). Masking preserves the non-identifying text and the row structure. |

Every default is overridable, including to **Keep**.

## 5. The decision UI

A panel between upload and analysis, using the existing `.cellgrid` / `.cell` components:

- A heading stating how many columns were flagged out of how many scanned.
- One cell per flagged column: name, detected entity types, hit rate, and a redacted preview.
- A three-way control per column: **Drop · Mask · Keep**, defaulted per §4.4.
- A single confirm action that applies the decisions and proceeds.

If nothing is flagged, no panel appears and the flow is unchanged — the feature is invisible on a
clean upload.

Choosing **Keep** is a deliberate, informed act. The UI states its consequence at the point of the
choice, not in a caveat afterwards: kept columns stay in the data, and their values are scrubbed on
the way to the model, but scrubbing depends on the model's span recall, which is unpublished.

## 6. What this is allowed to claim

The claim is assembled from what is verifiable at runtime, and it defaults to the **weaker**
statement so a misconfiguration cannot cause an overclaim.

- **Always:** "Identifiers were removed before anything reached the language model."
- **Additionally, only when the language model is genuinely on this machine:** "and with a local
  model, nothing left this machine."

The second line requires a **loopback check**, not the existing `llm._is_local()`. That helper is
named for a different question than the one asked here — its own docstring says it is True for
"Ollama, LM Studio, vLLM, **a free-tier API**", so a *remote* endpoint such as Groq or Together also
sets `OPENAI_BASE_URL` and would satisfy it. Asserting "nothing left this machine" on that basis
would be false precisely when it matters.

The check is therefore: parse `OPENAI_BASE_URL` and require the host to be `localhost`, `127.0.0.1`,
or `::1`. Anything else — unset, hosted OpenAI, or a remote custom endpoint — gets only the first
line. This defaults to the weaker claim and has no deployment flag to misconfigure.

**Never claimed, anywhere:** that the data is de-identified, HIPAA-compliant, safe to share, or
cleared for any regulatory purpose. On the hosted deploy the file has already reached Streamlit's
server before any of this runs, so the first half of the existing warning stays true and stays
on screen.

## 7. Failure modes — fail open, loudly

A privacy feature that breaks the app when it breaks is worse than one that reports being off.

| Failure | Behaviour |
|---|---|
| `openmed` not importable | `available()` is False; the panel is replaced by "de-identification unavailable"; upload proceeds under the existing warning |
| Model download fails on first use | Same, with the reason surfaced |
| `scan_columns` raises | Same; the exception is logged, not swallowed silently |

In every case the upload still works and the original warning is shown unmodified. The feature never
degrades to a *silent* no-op, because a user who believes scrubbing ran when it did not is worse off
than one who was told it is unavailable.

## 8. Testing

All tests mock `openmed`. **CI must not download a model** — that would make the suite depend on HF
Hub availability and add tens of megabytes to every run.

- `tests/test_deid.py` (new): `available()` returns False rather than raising when `openmed` is
  absent; `scan_columns` flags an obviously-identifying synthetic column and leaves a numeric one
  alone; `apply_decisions` drops and masks exactly the named columns and nothing else;
  `scrub_frame` touches only the named columns.
- **Regression guard:** `run_analysis` with `deid_columns=None` performs no de-id call at all —
  asserted by monkeypatching `deid.scrub_frame` to raise. This is the test that keeps the
  demo-warehouse path honest.
- `tests/test_userdata.py`: `build_catalog` example values pass through `scrub_values`.
- The UI panel is covered by an `AppTest` case in the existing smoke test.

**What the tests deliberately do not establish:** whether the model's recall is good enough on real
clinical text. Mocked tests verify plumbing, not detection quality — that is now supplied
separately by `agent/deid_eval.py`, which scores the model against Synthea's own generated
identifiers (200 patients, both the raw Synthea corpus and a normalised variant with Synthea's
synthetic markers stripped). Measured: normalised span recall **99.9%** overall (every entity type
at 100% except `first_name` at 99%, one survivor), raw span recall **100%**; column-level recall
**100%** (every identifier column flagged), column-level precision **70%** — a **floor, not the
model's true precision**, because the scoring counts the expected quasi-identifier flags on `age`
and `sex` as false positives by design (they must stay flagged-but-kept), plus one additional flag
on a clean column in the measured run. This is **not a governed-corpus figure**: the i2b2/n2c2
de-identification sets are the standard for that, though access-controlled, and Synthea's
distribution and templated notes are not real clinical text — real clinical text would very likely
score worse. Real-clinical-text recall stays an open question this benchmark does not answer, and
§6's wording reflects that.

## 9. Scope

**In:** `agent/deid.py`, the decision panel in the BYOD block, the `build_catalog` scrub, one
optional parameter on `run_analysis`, pinned `openmed` and `onnxruntime` in `requirements.txt`,
and the tests above.

**Out:** de-identification of the demo warehouse (it is synthetic — there is nothing to remove);
any change to the agent's behaviour when `deid_columns` is absent; any claim of compliance;
re-identification risk scoring or k-anonymity, which is a different and much larger problem;
measuring the model's recall, which is prerequisite to trusting it but not to building it.

## 10. Open risks

1. **Recall is measured only on a Synthea-derived corpus, not real clinical text**, and that stays
   the central risk. `agent/deid_eval.py` measured normalised span recall of **99.9%** and
   column-level recall of **100%** against 200 Synthea patients with templated notes (column
   precision floors at **70%**, understated by the expected `age`/`sex` quasi-identifier flags).
   The design mitigates the risk structurally — dropping a column does not depend on the model
   catching every cell — but a user who chooses Keep is relying on span detection measured on a
   synthetic, templated corpus; real clinical text, with its messier phrasing and formats, would
   very likely score worse.
2. **Dependency weight on Streamlit Cloud.** `openmed[hf]` pulls `transformers`; pin both it and
   `onnxruntime` and watch the first deploy, given this project's history of rebuild failures.
3. **First-use latency.** The 44M model downloads on the first upload of a session. Acceptable, and
   confined to users who actually upload, but it should be visible in the UI rather than looking
   like a hang.
