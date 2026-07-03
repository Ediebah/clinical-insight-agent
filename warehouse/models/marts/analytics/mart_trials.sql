-- mart_trials — synthetic clinical-trial outcomes for non-inferiority analysis (NOT real data).
-- Grain: one row per randomized subject. PK: subject_id.
-- Purpose: a clinically-framed dataset (treatment arm vs standard of care, a binary cure endpoint +
-- an adverse-event flag) so a non-inferiority question depicts an actual trial, not a product A/B.
-- Outcomes are deterministic hash-based pseudo-random (reproducible). Two scenarios:
--   antibiotic_ni  → new_drug cure ≈ standard_of_care  → NON-INFERIOR within a 10-point margin
--   device_ni      → new_device cure < standard_of_care → NOT non-inferior (worse beyond the margin)

with spec(trial, arm, n_subjects, cure_per_1000, ae_per_1000) as (
    values
        ('antibiotic_ni', 'standard_of_care', 1200, 850, 150),
        ('antibiotic_ni', 'new_drug',         1200, 840, 120),
        ('device_ni',  'standard_of_care',  600, 820, 100),
        ('device_ni',  'new_device',        600, 700, 130)
),

nums as (
    select unnest(generate_series(1, 1200)) as subject_seq
),

assign as (
    select s.trial, s.arm, s.cure_per_1000, s.ae_per_1000, n.subject_seq
    from spec s
    join nums n on n.subject_seq <= s.n_subjects
),

drawn as (
    select
        trial,
        arm,
        trial || '-' || arm || '-' || subject_seq          as subject_id,
        hash(trial || arm || subject_seq::varchar)          as h_cure,
        hash(trial || arm || subject_seq::varchar || 'ae')  as h_ae,
        cure_per_1000,
        ae_per_1000
    from assign
)

select
    trial,
    arm,
    subject_id,
    case when (h_cure % 1000) < cure_per_1000 then 1 else 0 end  as cured,
    case when (h_ae % 1000) < ae_per_1000 then 1 else 0 end      as adverse_event
from drawn
