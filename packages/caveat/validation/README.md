# Checks on public datasets

`validate_public_data.py` runs selected checks on three public UCI datasets in `examples/`:
Heart Disease, Heart Failure Clinical Records, and Breast Cancer Wisconsin Diagnostic. The
repository's [data provenance](../../../docs/DATA_PROVENANCE.md) and
[third-party notices](../../../THIRD_PARTY_NOTICES.md) describe their sources and terms.

```bash
python packages/caveat/validation/validate_public_data.py
```

The script compares nine outputs with calculations or expectations for these specific data. Some
checks reuse `caveat` helper functions, so the checks are not all independent numerical validation.
A passing run does not measure general accuracy, establish external clinical validity, or establish
that the library is safe for clinical decisions.

The stratified reversal regression test now uses constructed counts in
`tests/test_synthetic_strata.py`. It verifies role inference, a pooled contrast, a reversal warning,
and small-cell behavior. The earlier Berkeley table was removed from the current checkout because
its exact source and redistribution rights could not be established. That historical fixture remains
in earlier Git commits; removing it from the current checkout does not change repository history.
