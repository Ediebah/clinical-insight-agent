# Read-only data adapters

`agent.research.DataAdapter` is a small Python protocol: `read() -> pandas.DataFrame`. `DataFrameAdapter` copies an in-memory frame; `DuckDBAdapter` runs a validated read-only SQL query with external access disabled and refuses results above its cap.

```python
from agent.research import DuckDBAdapter, run_spec

adapter = DuckDBAdapter('non_sensitive.duckdb', 'select outcome, age from synthetic_cohort')
frame = adapter.read()
# In this direct mode the frame is already selected: set population='all rows',
# exclusions=[], sql='', and data_source='in-memory dataframe' in the specification.
result = run_spec(reviewed_specification, frame, approved=True)
```

An adapter contributes only data access: it does not define the study population, establish data quality, enforce a clinical data-use agreement, or authorize sensitive information. Direct DataFrame analysis rejects SQL and unapplied exclusions; the caller must retain the query used to construct the frame separately. `source_identity` is a caller assertion for in-memory data, not proof of provenance. The CSV CLI checks that its input path matches the specification. Implementations must preserve the source, return a DataFrame, fail clearly for incomplete/truncated data, and document the connection identity, supported types, resource limits, and any network access. Add isolated tests proving read-only behavior, failures, row limits, and output shape. See `tests/test_research_workflow.py`.

DuckDB is the only database implementation shipped here. In-memory data is supported. OMOP mapping and other engines require separately designed and tested adapters and are not supported by this interface today.
