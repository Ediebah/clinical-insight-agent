# Privacy and data flow

Only synthetic or otherwise non-sensitive information is supported. Do not upload PHI, patient records, credentials, or confidential information.

- Uploads arrive at the Streamlit server. Uploaded tables are materialized in a temporary DuckDB directory; removing the upload or switching sources triggers cleanup. Crashes and abandoned sessions may leave files until the host clears them.
- An optional identifier model samples up to 20 unique values per column. It can fail open or miss identifiers; it is not a de-identification guarantee. Model weights may be downloaded on first use.
- Column names and selected example values form the semantic catalog. Questions, catalog context, generated SQL, and previews or summaries may be sent to the configured model endpoint. A custom URL can be remote.
- Local JSONL logs can contain questions, generated SQL, and feedback. They have no authentication, tamper-evident storage, guaranteed retention, or tenant isolation.
- Research bundles exclude source rows by default and reject some obvious credential patterns. User text, SQL, model summaries, and model-generated text can still contain sensitive values. Inspect every artifact before sharing. Hashes can identify known data and are not anonymization.
- The read-only database controls reduce SQL filesystem access, but are not a security audit or a substitute for per-user access control, isolation, authorization, incident response, or vendor agreements.
