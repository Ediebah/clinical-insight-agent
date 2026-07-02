-- mart_experiments — synthetic product A/B experiment assignments (self-serve experiment analysis).
-- Grain: one row per user assignment. PK: assignment_id.
-- Purpose: gives the agent real experiment data to analyze (conversion + revenue by variant) so it can
-- draft ship / no-ship calls. Outcomes are DETERMINISTIC pseudo-random (hash-based) so the numbers are
-- reproducible across rebuilds. NOT clinical data — this illustrates the experiment-analysis capability.
-- Rates are baked per variant to span the interesting cases:
--   checkout_redesign  → treatment clearly wins        (ship)
--   pricing_page       → no detectable difference       (inconclusive / underpowered-looking)
--   aggressive_upsell  → treatment hurts conversion      (do not ship)
--   onboarding_email   → 3 variants                      (multiple comparisons → FDR)

with spec(experiment, variant, n_users, rate_per_1000) as (
    values
        ('checkout_redesign', 'control',   3000, 100),
        ('checkout_redesign', 'treatment', 3000, 132),
        ('pricing_page',      'control',   2500,  82),
        ('pricing_page',      'treatment', 2500,  85),
        ('aggressive_upsell', 'control',   2800, 120),
        ('aggressive_upsell', 'treatment', 2800,  98),
        ('onboarding_email',  'control',   2000, 150),
        ('onboarding_email',  'variant_b', 2000, 175),
        ('onboarding_email',  'variant_c', 2000, 156)
),

nums as (
    select unnest(generate_series(1, 3000)) as user_seq
),

assign as (
    select s.experiment, s.variant, s.rate_per_1000, n.user_seq
    from spec s
    join nums n on n.user_seq <= s.n_users
),

drawn as (
    select
        experiment,
        variant,
        experiment || '-' || variant || '-' || user_seq  as assignment_id,
        hash(experiment || variant || user_seq::varchar)  as h,
        rate_per_1000
    from assign
)

select
    experiment,
    variant,
    assignment_id,
    case when (h % 1000) < rate_per_1000 then 1 else 0 end                        as converted,
    case when (h % 1000) < rate_per_1000
         then round(20 + (hash(assignment_id || 'rev') % 15000) / 100.0, 2)
         else 0.0 end                                                            as revenue
from drawn
