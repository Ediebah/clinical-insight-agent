# Capability map

All methods are exploratory. Requirements below are minimum technical requirements, not guarantees of validity. The same patient appearing in multiple rows, non-random missingness, temporal leakage, selection, and unmeasured confounding need separate study-specific evaluation.

| Family | Inputs and assumptions | Evidence and limits |
|---|---|---|
| `caveat` | A result table; optional explicit column roles | Deterministic checks and small labeled examples. Role inference and warnings can miss problems or flag benign patterns. A confounding warning does not measure confounding. |
| Logistic / OLS | Outcome and predictors; independent observations, model-specific functional form | Unit tests and public-data regression comparisons. Data-driven selection and single imputation make coefficients and intervals exploratory. |
| Cox / Kaplan–Meier | Duration and event; relevant censoring and proportional-hazards assumptions | Synthetic tests and a public-data comparison. Check censoring and time origin. Competing-risk and repeated-measure models are unsupported. |
| Prediction / forest | Outcome, predictors, independent units; fold-safe preprocessing | Nested cross-validation evaluates selection internally. Fold variation is not a confidence interval; external, temporal, and subgroup validation remain necessary. |
| Survival ML | Duration, event, predictors; appropriate censoring and follow-up | Nested tuning reports concordance, time-dependent AUC, and integrated Brier score separately. Some metrics may be unavailable for a fold. Integrated Brier score is not a skill score. |
| Decision curve / failure analysis | Binary outcome and predictors | Out-of-fold predictions and nested automatic family selection. Risks can be miscalibrated. Curves from this prototype do not establish clinical utility. |
| Causal AIPW | Treatment, outcome, pre-treatment predictors | Cross-fitting and synthetic known-effect simulations. No unmeasured confounding, positivity, and other causal assumptions cannot be established from the data alone. Propensities are clipped, not participants trimmed. |
| Experiment / non-inferiority | Appropriate arms, outcome, design, and prespecified margin where applicable | Unit tests only; study design, multiplicity and selection can invalidate conclusions. |
| Sample size | Explicit endpoint and design assumptions | Deterministic calculation under the specified model; not a full statistical analysis plan. |
| Bayesian assurance / interim | Explicit priors, planned size, target, reference, and decision thresholds. Two-arm analyses also require a control Beta prior. | Binary conjugate outcome counts are enumerated; two-arm probability calculations use fixed-grid numerical integration. A control-density mass check is not an error bound. Control-prior parameters below one, underresolved control densities, and interim grids above 10,000 cells are unsupported. A lock hash does not prove timing. Standalone low-level primitives expose defaults and require expert review. |
| Published-design reproduction | Text-based PDF or plain text for supported single-arm binary design | Extracted values require review and source evidence. Unsupported designs, encrypted or scanned PDFs, and missing values must not be silently filled. |

No assurance is made for patient care, PHI, sensitive uploads, regulatory submissions, production multi-tenancy, general causal identification, competing-risk inference, or external clinical prediction performance.
