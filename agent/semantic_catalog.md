# Semantic Catalog

Generated from dbt artifacts. 16 tables, 6 named metrics.

## Named metrics

### `readmission_rate_30d`
- **Definition:** Share of index inpatient stays followed by another inpatient admission within 0-30 days of discharge.
- **Source model:** `mart_readmissions`
- **SQL:** `avg(is_30d_readmission::int)  -- optionally *100 for a percentage`
- **Caveats:** Inpatient-only. Denominator is index inpatient stays, not patients.

### `avg_encounter_cost`
- **Definition:** Average total billed cost across encounters.
- **Source model:** `fct_encounters`
- **SQL:** `avg(total_claim_cost)`
- **Caveats:** Billed (claim) cost, synthetic. Segment by encounter_class for fair comparisons.

### `avg_patient_out_of_pocket`
- **Definition:** Average amount the patient pays after insurance, per encounter.
- **Source model:** `fct_encounters`
- **SQL:** `avg(patient_out_of_pocket)  -- total_claim_cost - payer_coverage`
- **Caveats:** Synthetic payer logic; not real benefit design.

### `condition_prevalence_by_age`
- **Definition:** Percent of patients in an age band who have a given condition.
- **Source model:** `mart_condition_prevalence`
- **SQL:** `prevalence_pct  -- 100 * patients_with_condition / total_patients_in_age_group`
- **Caveats:** Small age bands (e.g. 75+, n≈91) give noisy estimates — check total_patients_in_age_group.

### `avg_diagnosing_encounter_cost_by_condition`
- **Definition:** Average cost of the encounter at which a condition was diagnosed, per condition.
- **Source model:** `mart_cost_by_condition`
- **SQL:** `avg_diagnosing_encounter_cost`
- **Caveats:** NOT lifetime cost of treating the condition — no causal attribution of downstream care.

### `total_medication_cost`
- **Definition:** Total cost of medication orders.
- **Source model:** `fct_medications`
- **SQL:** `sum(total_cost)`
- **Caveats:** Order-level synthetic cost; a patient may have many orders of one drug.

## Tables

### `dim_condition`  (core)
Condition-concept dimension. Grain: one row per SNOMED-CT condition_code.

- **Relation:** `healthcare.main.dim_condition`
- **Primary key:** condition_code

| column | type | description | examples |
|---|---|---|---|
| `condition_code` | VARCHAR | Primary key (SNOMED-CT code). | 237602007, 422650009, 127013003 |
| `condition_description` | VARCHAR |  | Carcinoma in situ of tongue, Encounter for other procedures for purposes other than remedying health state, Carcinoma in situ of larynx |
| `code_system` | VARCHAR |  | ICD10, SNOMED-CT |

### `dim_medication`  (core)
Medication-concept dimension. Grain: one row per RxNorm medication_code.

- **Relation:** `healthcare.main.dim_medication`
- **Primary key:** medication_code

| column | type | description | examples |
|---|---|---|---|
| `medication_code` | VARCHAR | Primary key (RxNorm code). | 351109, 1234995, 106892 |
| `medication_description` | VARCHAR |  | amoxicillin 875 MG / clavulanate 125 MG Oral Tablet, etoposide 100 MG Injection [Etopophos], proparacaine hydrochloride 5 MG/ML Ophthalmic Solution |

### `dim_organization`  (core)
Organization dimension. Grain: one row per organization_id.

- **Relation:** `healthcare.main.dim_organization`
- **Primary key:** organization_id

| column | type | description | examples |
|---|---|---|---|
| `organization_id` | VARCHAR | Primary key (UUID). |  |
| `organization_name` | VARCHAR |  | TRINITY FAMILY MEDICINE, CAREWELL URGENT CARE CENTERS OF MA  PC, LIFE CARE CENTER OF PLYMOUTH |
| `city` | VARCHAR |  | NORTH READING, SHARON, BOSTON |
| `state` | VARCHAR |  | MA |
| `zip_code` | VARCHAR |  | 012389645, 019704267, 019607938 |
| `latitude` | DOUBLE |  |  |
| `longitude` | DOUBLE |  |  |
| `revenue` | DOUBLE |  |  |
| `utilization` | INTEGER |  |  |

### `dim_patient`  (core)
Patient dimension. Grain: one row per patient. Adds derived age + clinical age bands.

- **Relation:** `healthcare.main.dim_patient`
- **Primary key:** patient_id

| column | type | description | examples |
|---|---|---|---|
| `patient_id` | VARCHAR | Primary key (UUID). |  |
| `birth_date` | DATE |  |  |
| `death_date` | DATE |  |  |
| `is_deceased` | BOOLEAN |  |  |
| `age` | DOUBLE | Age in years at death (if deceased) or as of the cohort's snapshot date (the latest date in the data). Non-negative by construction. |  |
| `age_group` | VARCHAR | Clinical age band. | 0-17, 40-64, 75+ |
| `gender` | VARCHAR |  | F, M |
| `race` | VARCHAR |  | white, native, other |
| `ethnicity` | VARCHAR |  | hispanic, nonhispanic |
| `marital_status` | VARCHAR |  | W, M, S |
| `city` | VARCHAR |  | Somerville, Hopkinton, Hudson |
| `state` | VARCHAR |  | Massachusetts |
| `county` | VARCHAR |  | Worcester County, Nantucket County, Suffolk County |
| `zip_code` | VARCHAR |  | 02134, 01904, 02155 |
| `healthcare_expenses` | DOUBLE |  |  |
| `healthcare_coverage` | DOUBLE |  |  |
| `income` | DOUBLE |  |  |

### `dim_payer`  (core)
Payer dimension. Grain: one row per payer_id.

- **Relation:** `healthcare.main.dim_payer`
- **Primary key:** payer_id

| column | type | description | examples |
|---|---|---|---|
| `payer_id` | VARCHAR | Primary key (UUID). |  |
| `payer_name` | VARCHAR |  | Dual Eligible, Medicare, UnitedHealthcare |
| `ownership` | VARCHAR |  | NO_INSURANCE, PRIVATE, GOVERNMENT |
| `state_headquartered` | VARCHAR |  |  |
| `amount_covered` | DOUBLE |  |  |
| `amount_uncovered` | DOUBLE |  |  |
| `revenue` | DOUBLE |  |  |
| `covered_encounters` | INTEGER |  |  |
| `uncovered_encounters` | INTEGER |  |  |

### `dim_provider`  (core)
Provider dimension with denormalized organization name. Grain: one row per provider_id.

- **Relation:** `healthcare.main.dim_provider`
- **Primary key:** provider_id

| column | type | description | examples |
|---|---|---|---|
| `provider_id` | VARCHAR | Primary key (UUID). |  |
| `provider_name` | VARCHAR |  | Huong243 Jakubowski832, Jasper743 Champlin946, Carylon722 Corwin846 |
| `gender` | VARCHAR |  | F, M |
| `specialty` | VARCHAR |  | GENERAL PRACTICE |
| `organization_id` | VARCHAR |  |  |
| `organization_name` | VARCHAR |  | BOSTON HEALTH CARE FOR THE HOMELESS PROGRAM INC, NURSE ON CALL, CAPE HERITAGE REHABILITATION & HEALTH CARE CENTER |
| `city` | VARCHAR |  | NORTH READING, SHARON, BOSTON |
| `state` | VARCHAR |  | MA |
| `zip_code` | VARCHAR |  | 021482329, 025328305, 014535768 |
| `encounter_count` | INTEGER |  |  |
| `procedure_count` | INTEGER |  |  |

### `fct_conditions`  (core)
Condition-episode fact. Grain: one row per patient-condition episode.

- **Relation:** `healthcare.main.fct_conditions`
- **Primary key:** condition_episode_id
- **Foreign keys:** patient_id → dim_patient.patient_id; condition_code → dim_condition.condition_code

| column | type | description | examples |
|---|---|---|---|
| `condition_episode_id` | VARCHAR | Surrogate primary key. |  |
| `patient_id` | VARCHAR |  |  |
| `condition_code` | VARCHAR |  | 59621000, 26929004, 44054006 |
| `encounter_id` | VARCHAR |  |  |
| `onset_date` | DATE |  |  |
| `resolved_date` | DATE |  |  |
| `is_active` | BOOLEAN |  |  |
| `duration_days` | BIGINT |  |  |

### `fct_encounters`  (core)
Encounter fact. Grain: one row per encounter. Measures: costs, out-of-pocket, duration.

- **Relation:** `healthcare.main.fct_encounters`
- **Primary key:** encounter_id
- **Foreign keys:** patient_id → dim_patient.patient_id; organization_id → dim_organization.organization_id; provider_id → dim_provider.provider_id; payer_id → dim_payer.payer_id

| column | type | description | examples |
|---|---|---|---|
| `encounter_id` | VARCHAR | Primary key (natural). |  |
| `patient_id` | VARCHAR |  |  |
| `organization_id` | VARCHAR |  |  |
| `provider_id` | VARCHAR |  |  |
| `payer_id` | VARCHAR |  |  |
| `encounter_date` | DATE |  |  |
| `encounter_start` | TIMESTAMP |  |  |
| `encounter_stop` | TIMESTAMP |  |  |
| `encounter_class` | VARCHAR |  | urgentcare, home, wellness |
| `encounter_code` | VARCHAR |  | 305408004, 453131000124105, 185349003 |
| `encounter_description` | VARCHAR |  | Urgent care clinic (environment), Admission to ward (procedure), Hospital admission  for observation (procedure) |
| `reason_code` | VARCHAR |  | 262521009, 58150001, 203646004 |
| `reason_description` | VARCHAR |  | Epidermal burn of skin (disorder), Seizure disorder (disorder), Tree nut (substance) |
| `base_encounter_cost` | DOUBLE |  |  |
| `total_claim_cost` | DOUBLE |  |  |
| `payer_coverage` | DOUBLE |  |  |
| `patient_out_of_pocket` | DOUBLE |  |  |
| `duration_minutes` | BIGINT |  |  |

### `fct_medications`  (core)
Medication-order fact. Grain: one row per medication order.

- **Relation:** `healthcare.main.fct_medications`
- **Primary key:** medication_order_id
- **Foreign keys:** patient_id → dim_patient.patient_id; medication_code → dim_medication.medication_code

| column | type | description | examples |
|---|---|---|---|
| `medication_order_id` | VARCHAR | Surrogate primary key. |  |
| `patient_id` | VARCHAR |  |  |
| `medication_code` | VARCHAR |  | 849574, 1049504, 1049625 |
| `payer_id` | VARCHAR |  |  |
| `encounter_id` | VARCHAR |  |  |
| `dispense_start` | TIMESTAMP |  |  |
| `dispense_stop` | TIMESTAMP |  |  |
| `is_active` | BOOLEAN |  |  |
| `base_cost` | DOUBLE |  |  |
| `payer_coverage` | DOUBLE |  |  |
| `dispenses` | INTEGER |  |  |
| `total_cost` | DOUBLE |  |  |
| `days_supplied` | BIGINT | Days between dispense start and stop; null when ongoing or the source span is invalid (stop before start). |  |

### `fct_observations`  (core)
Observation fact (labs/vitals/survey). Grain: one row per measurement.

- **Relation:** `healthcare.main.fct_observations`
- **Primary key:** observation_id
- **Foreign keys:** patient_id → dim_patient.patient_id

| column | type | description | examples |
|---|---|---|---|
| `observation_id` | VARCHAR | Surrogate primary key. |  |
| `patient_id` | VARCHAR |  |  |
| `encounter_id` | VARCHAR |  |  |
| `observed_at` | TIMESTAMP |  |  |
| `observation_category` | VARCHAR |  | survey, laboratory, imaging |
| `observation_code` | VARCHAR |  | 55758-7, 5804-0, 93029-7 |
| `observation_description` | VARCHAR |  | Body mass index (BMI) [Ratio], pH of Urine by Test strip, Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma |
| `value_text` | VARCHAR |  | 21.7, 28.6, 77.0 |
| `value_numeric` | DOUBLE |  |  |
| `units` | VARCHAR |  | {score}, kg/m2, pg/mL |
| `value_type` | VARCHAR |  | numeric, text |

### `fct_procedures`  (core)
Procedure fact. Grain: one row per procedure performed.

- **Relation:** `healthcare.main.fct_procedures`
- **Primary key:** procedure_event_id
- **Foreign keys:** patient_id → dim_patient.patient_id

| column | type | description | examples |
|---|---|---|---|
| `procedure_event_id` | VARCHAR | Surrogate primary key. |  |
| `patient_id` | VARCHAR |  |  |
| `procedure_code` | VARCHAR |  | 223495004, 269911007, D0330 |
| `encounter_id` | VARCHAR |  |  |
| `procedure_start` | TIMESTAMP |  |  |
| `procedure_stop` | TIMESTAMP |  |  |
| `base_cost` | DOUBLE |  |  |
| `reason_code` | VARCHAR |  | 1231000119100, 267020005, 37849005 |
| `reason_description` | VARCHAR |  | Chronic obstructive bronchitis (disorder), Dependent drug abuse (disorder), Laceration of forearm (disorder) |

### `mart_condition_prevalence`  (analytics)
Condition prevalence by patient age band. One row per (condition_code, age_group). Small age bands make rare-condition estimates noisy — total_patients_in_age_group is the denominator, exposed so consumers can judge reliability.

- **Relation:** `healthcare.main.mart_condition_prevalence`
- **Primary key:** condition_code, age_group

| column | type | description | examples |
|---|---|---|---|
| `condition_code` | VARCHAR |  | 73438004, 160904001, 161744009 |
| `condition_description` | VARCHAR |  | Carcinoma in situ of tongue, Encounter for other procedures for purposes other than remedying health state, Carcinoma in situ of larynx |
| `age_group` | VARCHAR |  | 0-17, 18-39, 75+ |
| `patients_with_condition` | BIGINT |  |  |
| `total_patients_in_age_group` | BIGINT |  |  |
| `prevalence_pct` | DOUBLE | 100 * patients_with_condition / total_patients_in_age_group. |  |

### `mart_cost_by_condition`  (analytics)
Cost of the diagnosing encounter aggregated by condition (NOT lifetime cost of care). One row per condition_code.

- **Relation:** `healthcare.main.mart_cost_by_condition`
- **Primary key:** condition_code
- **Foreign keys:** condition_code → dim_condition.condition_code

| column | type | description | examples |
|---|---|---|---|
| `condition_code` | VARCHAR | PK — SNOMED-CT condition code. | 4356008, 1085951000119102, 22253000 |
| `condition_description` | VARCHAR |  | Gingival recession, Pneumonia (disorder), Excessive attrition of teeth |
| `num_episodes` | BIGINT |  |  |
| `num_patients` | BIGINT | Distinct patients who have this condition. |  |
| `total_diagnosing_encounter_cost` | DOUBLE |  |  |
| `avg_diagnosing_encounter_cost` | DOUBLE |  |  |

### `mart_experiments`  (analytics)
Synthetic product A/B experiment assignments (conversion + revenue by variant), so the agent can draft ship / no-ship calls. One row per user assignment; outcomes are deterministic hash-based pseudo-random (reproducible). Illustrative, not clinical data.

- **Relation:** `healthcare.main.mart_experiments`
- **Primary key:** assignment_id

| column | type | description | examples |
|---|---|---|---|
| `experiment` | VARCHAR | Experiment name (e.g. checkout_redesign). | aggressive_upsell, pricing_page, checkout_redesign |
| `variant` | VARCHAR | The arm the user was assigned to (control / treatment / variant_b …). | variant_b, variant_c, control |
| `assignment_id` | VARCHAR | PK — one user's assignment to an experiment variant. |  |
| `converted` | INTEGER | 1 if the user converted, else 0 (the primary binary metric). |  |
| `revenue` | DOUBLE | Revenue for converted users, else 0 (a continuous secondary metric). |  |

### `mart_readmissions`  (analytics)
30-day inpatient readmission flags. One row per index inpatient encounter the patient survived to discharge (died-in-stay admissions are excluded from the denominator, per standard readmission measures); is_30d_readmission is true when the same patient is admitted again strictly after discharge and within a 1-30 day window (a same-day transfer / overlapping stay is not a readmission). The candidate is the earliest admission strictly after discharge on a later calendar day, so an overlapping or same-day stay cannot hide a later qualifying readmission.

- **Relation:** `healthcare.main.mart_readmissions`
- **Primary key:** index_encounter_id
- **Foreign keys:** patient_id → dim_patient.patient_id

| column | type | description | examples |
|---|---|---|---|
| `index_encounter_id` | VARCHAR | PK — the index inpatient encounter. |  |
| `patient_id` | VARCHAR |  |  |
| `admission_date` | TIMESTAMP |  |  |
| `discharge_date` | TIMESTAMP |  |  |
| `next_admission_start` | TIMESTAMP |  |  |
| `days_to_next_admission` | BIGINT | Calendar days from discharge to the earliest subsequent inpatient admission on a later calendar day; null when no such admission exists. Same-day and overlapping stays are excluded. |  |
| `is_30d_readmission` | BOOLEAN | True if a subsequent inpatient admission occurred within 30 days of discharge. |  |
| `total_claim_cost` | DOUBLE |  |  |

### `mart_trials`  (analytics)
Synthetic clinical-trial outcomes (treatment arm vs standard of care; a binary cure endpoint + an adverse-event flag) for non-inferiority analysis. One row per randomized subject. Deterministic hash-based pseudo-random. NOT real data.

- **Relation:** `healthcare.main.mart_trials`
- **Primary key:** subject_id

| column | type | description | examples |
|---|---|---|---|
| `trial` | VARCHAR | Trial name (antibiotic_ni, device_ni). | device_ni, antibiotic_ni |
| `arm` | VARCHAR | Randomized arm (standard_of_care / new_drug / new_device). | new_drug, standard_of_care, new_device |
| `subject_id` | VARCHAR | PK — one randomized subject. |  |
| `cured` | INTEGER | 1 if the subject met the cure endpoint, else 0. |  |
| `adverse_event` | INTEGER | 1 if the subject had an adverse event, else 0. |  |
