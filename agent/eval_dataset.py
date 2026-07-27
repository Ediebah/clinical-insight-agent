"""GOLD — the single labeled ground-truth dataset shared by every eval.

Each case carries whatever the different evals need:
  * reference_sql / is_rate      → accuracy eval (deterministic ground-truth value)
  * expected_tables              → retrieval precision/recall/MRR
  * expect_clarification         → clarify-gate eval
One dataset, many metrics — so labels never drift between evals.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Gold:
    id: str
    question: str
    category: str
    reference_sql: str = ""
    is_rate: bool = False
    expected_tables: tuple[str, ...] = ()
    expect_clarification: bool = False


GOLD: list[Gold] = [
    # ---- counts ----
    Gold("n_patients", "How many patients are in the warehouse?", "count",
         "select count(*) from dim_patient", expected_tables=("dim_patient",)),
    Gold("n_deceased", "How many patients are deceased?", "count",
         "select count(*) from dim_patient where is_deceased", expected_tables=("dim_patient",)),
    Gold("n_inpatient", "How many inpatient encounters are there?", "count",
         "select count(*) from fct_encounters where encounter_class = 'inpatient'",
         expected_tables=("fct_encounters",)),
    Gold("n_conditions", "How many distinct conditions are recorded?", "count",
         "select count(*) from dim_condition", expected_tables=("dim_condition",)),
    Gold("n_med_orders", "What is the total number of medication orders?", "count",
         "select count(*) from fct_medications", expected_tables=("fct_medications",)),
    Gold("n_encounters", "How many encounters are there in total?", "count",
         "select count(*) from fct_encounters", expected_tables=("fct_encounters",)),
    Gold("n_providers", "How many providers are in the warehouse?", "count",
         "select count(*) from dim_provider", expected_tables=("dim_provider",)),
    Gold("n_female", "How many female patients are there?", "count",
         "select count(*) from dim_patient where gender = 'F'", expected_tables=("dim_patient",)),
    # ---- condition (lay-term vocabulary grounding: the agent must map the spoken term to the real
    #      SNOMED descriptions AND count DISTINCT patients, not sum per-description totals) ----
    Gold("copd_patients", "How many patients have COPD?", "condition",
         "select count(distinct f.patient_id) from fct_conditions f "
         "join dim_condition c on f.condition_code = c.condition_code "
         "where c.condition_description ilike '%chronic obstructive bronchitis%' "
         "or c.condition_description ilike '%emphysema%'",
         expected_tables=("fct_conditions", "dim_condition")),
    Gold("heart_attack_patients", "How many patients have had a heart attack?", "condition",
         "select count(distinct f.patient_id) from fct_conditions f "
         "join dim_condition c on f.condition_code = c.condition_code "
         "where c.condition_description ilike '%myocardial infarction%'",
         expected_tables=("fct_conditions", "dim_condition")),
    # ---- cost ----
    Gold("avg_cost", "What is the average total claim cost per encounter?", "cost",
         "select round(avg(total_claim_cost), 2) from fct_encounters", expected_tables=("fct_encounters",)),
    Gold("max_cost", "What is the most expensive encounter's total claim cost?", "cost",
         "select round(max(total_claim_cost), 2) from fct_encounters", expected_tables=("fct_encounters",)),
    Gold("avg_inpatient_cost", "What is the average claim cost of an inpatient encounter?", "cost",
         "select round(avg(total_claim_cost), 2) from fct_encounters where encounter_class = 'inpatient'",
         expected_tables=("fct_encounters",)),
    Gold("total_med_cost", "What is the total cost of all medication orders?", "cost",
         "select round(sum(total_cost), 0) from fct_medications", expected_tables=("fct_medications",)),
    # ---- rates ----
    Gold("readmit_rate", "What is the overall 30-day readmission rate as a percent?", "rate",
         "select round(100 * avg(is_30d_readmission::int), 1) from mart_readmissions",
         is_rate=True, expected_tables=("mart_readmissions",)),
    Gold("htn_65_74", "What is the prevalence of hypertension in the 65-74 age group, as a percent?", "rate",
         "select round(prevalence_pct, 1) from mart_condition_prevalence "
         "where condition_description ilike '%hypertension%' and age_group = '65-74'",
         is_rate=True, expected_tables=("mart_condition_prevalence",)),
    Gold("pct_deceased", "What percent of patients are deceased?", "rate",
         "select round(100.0 * avg(is_deceased::int), 1) from dim_patient",
         is_rate=True, expected_tables=("dim_patient",)),
    # ---- filter by clinical name ----
    Gold("n_diabetes_pts", "How many patients have a diabetes diagnosis?", "filter_name",
         "select count(distinct c.patient_id) from fct_conditions c join dim_condition d "
         "using (condition_code) where d.condition_description ilike '%diabetes%'",
         expected_tables=("fct_conditions", "dim_condition")),
    # ---- descriptive stat ----
    Gold("avg_age", "What is the average patient age?", "stat",
         "select round(avg(age), 1) from dim_patient", expected_tables=("dim_patient",)),
    # ---- more counts ----
    Gold("n_organizations", "How many healthcare organizations are there?", "count",
         "select count(*) from dim_organization", expected_tables=("dim_organization",)),
    Gold("n_payers", "How many insurance payers are there?", "count",
         "select count(*) from dim_payer", expected_tables=("dim_payer",)),
    Gold("n_male", "How many male patients are there?", "count",
         "select count(*) from dim_patient where gender = 'M'", expected_tables=("dim_patient",)),
    Gold("n_meds_distinct", "How many distinct medications are recorded?", "count",
         "select count(*) from dim_medication", expected_tables=("dim_medication",)),
    Gold("n_emergency", "How many emergency encounters are there?", "count",
         "select count(*) from fct_encounters where encounter_class = 'emergency'",
         expected_tables=("fct_encounters",)),
    Gold("n_procedures", "How many procedures were performed?", "count",
         "select count(*) from fct_procedures", expected_tables=("fct_procedures",)),
    # ---- more cost ----
    Gold("avg_med_cost", "What is the average total cost of a medication order?", "cost",
         "select round(avg(total_cost), 2) from fct_medications", expected_tables=("fct_medications",)),
    Gold("avg_procedure_cost", "What is the average base cost of a procedure?", "cost",
         "select round(avg(base_cost), 2) from fct_procedures", expected_tables=("fct_procedures",)),
    Gold("total_encounter_cost", "What is the total claim cost across all encounters?", "cost",
         "select round(sum(total_claim_cost), 0) from fct_encounters", expected_tables=("fct_encounters",)),
    # ---- more rates ----
    Gold("pct_female", "What percent of patients are female?", "rate",
         "select round(100.0 * avg((gender = 'F')::int), 1) from dim_patient",
         is_rate=True, expected_tables=("dim_patient",)),
    Gold("pct_inpatient", "What percent of encounters are inpatient?", "rate",
         "select round(100.0 * avg((encounter_class = 'inpatient')::int), 1) from fct_encounters",
         is_rate=True, expected_tables=("fct_encounters",)),
    # ---- more filter-by-name ----
    Gold("n_htn_pts", "How many patients have hypertension?", "filter_name",
         "select count(distinct c.patient_id) from fct_conditions c join dim_condition d "
         "using (condition_code) where d.condition_description ilike '%hypertension%'",
         expected_tables=("fct_conditions", "dim_condition")),
    # ---- more descriptive stat ----
    Gold("oldest_age", "What is the age of the oldest patient?", "stat",
         "select max(age) from dim_patient", expected_tables=("dim_patient",)),
    Gold("avg_enc_duration", "What is the average encounter duration in minutes?", "stat",
         "select round(avg(duration_minutes), 1) from fct_encounters", expected_tables=("fct_encounters",)),

    # ---- clarify gate ----
    Gold("ambiguous_trends", "show me the trends", "clarify", expect_clarification=True),
    Gold("out_of_scope", "which treatment is clinically best?", "clarify", expect_clarification=True),
]

ANSWERABLE = [g for g in GOLD if not g.expect_clarification]
CLARIFY = [g for g in GOLD if g.expect_clarification]


# ---------------------------------------------------------------------------------------------
# ROUTES — labelled ground truth for the INFERENTIAL router (agent._route).
#
# GOLD covers the aggregation path, where ground truth is a scalar from reference SQL. The router
# picks one of ~17 model types and there is no scalar to check: the ground truth IS the label. Kept
# in this module (not a separate file) so every eval's labels stay in one place, but as its own list
# so the accuracy eval's ANSWERABLE stays purely aggregational.
#
# A misroute is the agent's most dangerous silent failure: it does not error, it returns a
# confident, well-rendered model of the WRONG KIND. `why` records the near-neighbour each case
# discriminates against — those are the pairs agent._route's prompt spends its "prefer X over Y"
# rules on, and therefore the ones a prompt edit is most likely to break.
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Route:
    id: str
    question: str
    expected: str            # model_type from agent._fit_model, or "aggregate" for no-model
    why: str = ""            # the near-neighbour this case discriminates against


ROUTES: list[Route] = [
    # ---- logistic: binary outcome in a FIXED window ----
    Route("lg_adjusted_or",
          "What are the adjusted odds of 30-day readmission for patients with diabetes, "
          "controlling for age and sex?", "logistic",
          "not forest — the user wants an adjusted odds ratio, not variable importance"),
    Route("lg_binary_window",
          "Is hypertension associated with 30-day readmission after adjusting for age?", "logistic",
          "not survival — a fixed 30-day window has no varying event time"),

    # ---- ols: continuous outcome ----
    Route("ols_cost_regression",
          "Run a regression of total encounter cost on age and encounter class.", "ols",
          "not logistic — cost is continuous"),
    Route("ols_effect_on_cost",
          "What is the effect of hypertension on encounter cost, adjusting for age?", "ols",
          "not causal — no named intervention, just an adjusted association on a continuous outcome"),

    # ---- survival: time-to-event ----
    Route("sv_km_by_sex", "Compare survival curves by sex.", "survival",
          "not logistic — Kaplan-Meier needs duration + event"),
    Route("sv_hazard_ratio",
          "What is the hazard ratio for sex on mortality, adjusting for age?", "survival",
          "not logistic — hazard ratios are a Cox model"),
    Route("sv_timing_varies", "How does time to death vary by sex?", "survival",
          "not logistic — the prompt's rule: prefer survival when event TIMING varies"),

    # ---- survival_ml: ML survival / survival-model comparison ----
    Route("sml_best_survival",
          "Which survival model best fits mortality — Cox or a random survival forest?", "survival_ml",
          "not survival — the user asked for the BEST survival model, not one fit"),
    Route("sml_rsf", "Fit a random survival forest for mortality.", "survival_ml",
          "not survival — explicitly a machine-learning survival model"),

    # ---- association: two variables ----
    Route("as_correlation", "Is age correlated with total encounter cost?", "association",
          "not ols — two variables, no adjustment set"),
    Route("as_chi_square", "Is gender associated with having hypertension?", "association",
          "not logistic — a plain two-variable test, nothing to adjust for"),

    # ---- forest: variable importance ----
    Route("fr_feature_importance", "Show feature importance for 30-day readmission.", "forest",
          "not best_model — importance only, no model competition"),
    Route("fr_risk_factors",
          "What are the strongest risk factors for readmission?", "forest",
          "not logistic — 'strongest risk factors' is the prompt's forest trigger"),

    # ---- best_model: cross-validated model selection ----
    Route("bm_which_model", "Which model best predicts 30-day readmission?", "best_model",
          "not forest — the prompt's rule: prefer best_model when the user wants THE BEST model"),
    Route("bm_leaderboard",
          "Build the best predictive model for readmission and show me the leaderboard.", "best_model",
          "not forest — a leaderboard implies comparing candidates"),

    # ---- decision_curve ----
    Route("dc_net_benefit",
          "What is the net benefit of the readmission model across decision thresholds?",
          "decision_curve", "not failure_analysis — net benefit is decision-curve analysis"),
    Route("dc_worth_acting_on",
          "Is the readmission model worth acting on clinically?", "decision_curve",
          "not failure_analysis — clinical utility is the decision-curve question"),

    # ---- failure_analysis ----
    Route("fa_where_fail", "Where does the readmission model fail?", "failure_analysis",
          "not decision_curve — error analysis, not net benefit"),
    Route("fa_calibration",
          "Is the readmission model well calibrated, and which subgroup does it get wrong most?",
          "failure_analysis", "not decision_curve — calibration is the failure-analysis trigger"),

    # ---- timeseries ----
    Route("ts_forecast", "Forecast monthly encounter volume for the next 12 months.", "timeseries",
          "not ols — a forecast needs one row per PERIOD"),
    Route("ts_seasonal", "What is the seasonal trend in monthly admissions?", "timeseries",
          "not aggregate — seasonality is a time-series decomposition"),

    # ---- causal: named intervention + confounders → T-learner uplift ----
    Route("cs_coverage_mortality",
          "What is the effect of having insurance coverage on mortality, adjusting for age and sex?",
          "causal",
          "not survival — the prompt's rule: prefer causal when an INTERVENTION is named, "
          "even when the outcome is mortality"),
    Route("cs_drug_effect",
          "What is the causal effect of being on the drug versus not on readmission, "
          "controlling for comorbidity?", "causal",
          "not logistic — a named binary exposure with confounders is the uplift path"),

    # ---- experiment: A/B ----
    Route("ex_ab_test",
          "Analyse the checkout_redesign experiment — did variant B lift conversion?", "experiment",
          "not association — an A/B test has an assignment column and a metric"),
    Route("ex_should_we_ship", "Should we ship variant B of the checkout redesign?", "experiment",
          "not noninferiority — a superiority ship decision, no margin given"),

    # ---- noninferiority ----
    Route("ni_antibiotic",
          "Is the new antibiotic non-inferior to standard care within a 10% margin?", "noninferiority",
          "not experiment — an explicit NI margin makes this a non-inferiority test"),
    Route("ni_device_margin",
          "Is the device arm non-inferior on cure rate with a 5-point margin?", "noninferiority",
          "not sample_size — this analyses collected data, it is not a design calculation"),

    # ---- sample_size: design-stage frequentist power ----
    Route("ss_per_arm",
          "How many patients per arm do we need to detect a 10-point improvement from 60% "
          "with 80% power?", "sample_size",
          "not assurance — a frequentist power calculation, not a Bayesian go/no-go"),
    Route("ss_noninferiority_design",
          "What sample size do we need for a non-inferiority trial with a 10% margin and a "
          "70% control response rate?", "sample_size",
          "not noninferiority — DESIGN stage, there is no data to analyse yet"),

    # ---- assurance: design-stage Bayesian go/no-go (no data) ----
    Route("au_phase2",
          "What is the probability a 100-patient Phase II succeeds if Phase I showed "
          "8 of 20 responses?", "assurance",
          "not interim — nothing has been observed in THIS trial yet"),
    Route("au_two_arm",
          "We plan a randomized 200-patient trial against a 35% control rate, hoping for a "
          "15-point benefit. Phase I showed 14 of 20. What is the assurance?", "assurance",
          "not interim — a design calculation for a trial not yet run"),
    Route("au_device_goal",
          "Our device needs a success rate above 85%. Is the 120-patient study worth running?",
          "assurance", "not sample_size — a performance-goal go/no-go, not a power calculation"),

    # ---- interim: Bayesian go/no-go on data so far ----
    Route("in_futility",
          "We are 40 patients into a 100-patient trial with 12 responses. "
          "Continue or stop for futility?", "interim",
          "not assurance — patients have already been observed"),
    Route("in_predictive_probability",
          "We have 12 responses in the first 40 of a planned 100. What is the predictive "
          "probability of success?", "interim",
          "not assurance — predictive probability conditions on observed data"),
    Route("in_two_arm",
          "At the interim we have 18 of 40 on the drug and 10 of 38 on control, planning 200 "
          "total. Should we continue?", "interim",
          "not experiment — a Bayesian interim decision, not a completed A/B analysis"),

    # ---- aggregate: passes the _MODEL_HINT gate but needs no model ----
    Route("ag_experiment_count",
          "How many rows are in the experiments mart?", "aggregate",
          "'experiment' trips the gate, but this is a plain count"),
    Route("ag_list_variants",
          "List the distinct variants in the checkout_redesign experiment.", "aggregate",
          "'variant'/'experiment' trip the gate, but this is a plain SELECT DISTINCT"),
    Route("ag_adjusted_filter",
          "Adjust the encounter list to exclude cancelled visits and give me the total count.",
          "aggregate", "'adjust' trips the gate, but this is a filtered count"),

    # ---- model-shaped but subject-less: must be handed back, not guessed at ----
    # The gate runs BEFORE _triage so a specific model question isn't clarified away as vague. The
    # cost is that a vague one skips the clarify gate too. Routing these to 'aggregate' returns them
    # to _triage, which asks. Paired with GOLD's `ambiguous_trends`, which asserts the clarification
    # actually comes back out of the full agent.
    Route("ag_vague_trends", "show me the trends", "aggregate",
          "not timeseries — 'trend' trips the gate but no metric is named to forecast"),
    Route("ag_vague_correlations", "any correlations?", "aggregate",
          "not association — 'correlat' trips the gate but neither variable is named"),
]

# model_type → spec keys agent._fit_model indexes directly (a missing key is a fit-time failure)
ROUTE_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "logistic": ("outcome",),
    "ols": ("outcome",),
    "survival": ("duration", "event"),
    "cox": ("duration", "event"),
    "association": ("var_a", "var_b"),
    "forest": ("outcome",),
    "best_model": ("outcome",),
    "survival_ml": ("duration", "event"),
    "decision_curve": ("outcome",),
    "failure_analysis": ("outcome",),
    "timeseries": ("time_col", "value_col"),
    "causal": ("outcome", "treatment"),
    "experiment": ("group", "outcome"),
    "noninferiority": ("group", "outcome"),
    "interim": ("outcome", "n_planned"),
    "assurance": ("n_planned", "tv", "lrv"),
    "sample_size": ("outcome_type",),
    "aggregate": (),
}

# Design-stage calculations are dispatched BEFORE the analytic_sql check in agent.run_analysis, so
# they must NOT carry SQL. Every other model type must, or line ~700 silently drops it to the
# aggregate path with the right model_type already chosen — a misroute that looks like a success.
ROUTE_NO_SQL = {"sample_size", "assurance", "aggregate"}


# ---------------------------------------------------------------------------------------------
# BAYES — numeric ground truth for the Bayesian go/no-go layer.
#
# ROUTES checks the agent reaches the right MODEL. This checks it reaches the right NUMBER, which
# is a different failure: routing correctly to `assurance` and then reading 30% as the LRV instead
# of the TV produces a confident GO on a trial that should stop, and nothing in the routing eval
# would notice.
#
# bayes.py is closed-form conjugate, so the reference is computed by calling the same modeling
# entry point with the CORRECT parameters at eval time — deliberately not hardcoded. Hardcoding
# would re-test bayes.py (which has its own unit suite) and would rot whenever a grid legitimately
# changes. Computing it live isolates the one thing the agent actually controls here: pulling
# n_planned / tv / lrv / the prior out of English. A numeric mismatch is therefore an EXTRACTION
# bug, never an arithmetic one.
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BayesCase:
    id: str
    question: str
    fn: str                                       # "assurance" (design) | "interim" (data so far)
    expected_call: str                            # GO | CONSIDER | STOP
    metric: str                                   # verdict key to compare numerically
    params: dict                                  # ground-truth kwargs for the modeling entry point
    observed: dict = field(default_factory=dict)  # interim only: the counts the question states
    why: str = ""


BAYES: list[BayesCase] = [
    # ---- design-stage assurance (no data) ----
    BayesCase(
        "bo_assurance_phase2",
        "We are planning a 100-patient single-arm Phase II. Phase I showed 8 responses in 20 "
        "patients. We are hoping for a 30% response rate, and 15% is the minimum worth pursuing. "
        "What is the assurance?",
        fn="assurance", expected_call="GO", metric="assurance",
        params=dict(n_planned=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20),
        why="the plain case: every parameter is stated explicitly"),
    BayesCase(
        "bo_assurance_futile",
        "Should we run a 60-patient study? Our earlier work showed only 2 responses in 20. We "
        "would need a 40% response rate for this to be worth it, and below 25% we walk away.",
        fn="assurance", expected_call="STOP", metric="assurance",
        params=dict(n_planned=60, tv=0.40, lrv=0.25, prior_successes=2, prior_n=20),
        why="TV/LRV given as 'need' and 'walk away' rather than named — easy to swap"),
    BayesCase(
        "bo_assurance_device_goal",
        "Our device has to beat an 85% success rate to meet its performance goal. Bench testing "
        "showed 44 successes in 50. Is the planned 120-patient study worth running?",
        fn="assurance", expected_call="CONSIDER", metric="assurance",
        params=dict(n_planned=120, tv=0.85, lrv=0.85, framing="single_arm",
                    prior_successes=44, prior_n=50),
        why="a performance goal sets TV *and* LRV to the same value — the prompt's device rule"),
    BayesCase(
        "bo_assurance_two_arm",
        "We plan a randomized 200-patient trial against standard of care, which responds 35% of "
        "the time. We are hoping for a 15-point benefit, and any benefit at all is the floor. "
        "Phase I showed 14 responses in 20 on the drug. What is the assurance?",
        fn="assurance", expected_call="GO", metric="assurance",
        params=dict(framing="two_arm", n_planned=200, tv=0.15, lrv=0.0, control_rate=0.35,
                    prior_successes=14, prior_n=20),
        why="two-arm TV/LRV are RISK DIFFERENCES, not response rates — the classic mix-up"),

    # ---- interim on data so far ----
    BayesCase(
        "bo_interim_consider",
        "We are 40 patients into a planned 100-patient trial with 12 responses. We are hoping for "
        "a 30% response rate and 15% is the minimum worth pursuing. Continue or stop?",
        fn="interim", expected_call="CONSIDER", metric="predictive_prob",
        params=dict(n_planned=100, tv=0.30, lrv=0.15), observed=dict(successes=12, n_observed=40),
        why="n_planned (100) must not be confused with the 40 observed so far"),
    BayesCase(
        "bo_interim_futility",
        "We have 3 responses in the first 30 patients of a planned 120-patient trial. The target "
        "is a 30% response rate and 15% is the minimum worth pursuing. Should we stop for futility?",
        fn="interim", expected_call="STOP", metric="predictive_prob",
        params=dict(n_planned=120, tv=0.30, lrv=0.15), observed=dict(successes=3, n_observed=30),
        why="the futility signal that actually stops a trial — a false CONSIDER here costs money"),
    BayesCase(
        "bo_interim_go",
        "We are 40 patients into a planned 100-patient trial with 28 responses. The target is 30% "
        "and 15% is the minimum worth pursuing. Should we continue?",
        fn="interim", expected_call="GO", metric="predictive_prob",
        params=dict(n_planned=100, tv=0.30, lrv=0.15), observed=dict(successes=28, n_observed=40),
        why="the GO end of the scale, where predictive probability saturates at 1.0"),
    BayesCase(
        "bo_interim_two_arm",
        "At the interim we have 18 responses in 40 on the drug and 10 in 38 on control, in a "
        "planned 200-patient randomized trial. We are hoping for a 15-point benefit and any "
        "benefit is the floor. Should we continue?",
        fn="interim", expected_call="CONSIDER", metric="predictive_prob",
        params=dict(n_planned=200, tv=0.15, lrv=0.0, framing="two_arm",
                    group="arm", control="control"),
        observed=dict(t_successes=18, t_n=40, c_successes=10, c_n=38),
        why="both arms must be parsed AND the effect expressed as a difference"),
]
