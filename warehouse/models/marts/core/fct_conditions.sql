-- fct_conditions — grain: one row per patient-condition episode. No natural key, so we mint a
-- deterministic surrogate PK from the grain columns. (patient, condition, onset_date) is NOT unique
-- on its own (a patient can have two same-day diagnoses of the same condition), so we add a
-- deterministic row_number() within the grain group — the same guard fct_medications/fct_procedures/
-- fct_observations use. This guarantees a unique PK without dropping any rows.
-- FKs: patient, condition, encounter.

with conditions as (
    select * from {{ ref('stg_conditions') }}
),

keyed as (
    select
        *,
        row_number() over (
            partition by patient_id, condition_code, onset_date
            order by encounter_id, resolved_date, is_active
        ) as row_in_grain
    from conditions
)

select
    {{ dbt_utils.generate_surrogate_key(['patient_id', 'condition_code', 'onset_date', 'row_in_grain']) }}
                                                    as condition_episode_id,
    patient_id,
    condition_code,
    encounter_id,
    onset_date,
    resolved_date,
    is_active,
    date_diff('day', onset_date, resolved_date)     as duration_days   -- null if unresolved
from keyed
