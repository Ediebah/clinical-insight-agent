-- Singular test guarding the 30-day readmission flag (mart_readmissions.is_30d_readmission)
-- in BOTH directions. dbt singular tests fail when the query returns any rows.
--
--   Direction 1 (false positives): a flagged readmission MUST have its next inpatient admission
--   start STRICTLY AFTER discharge and land within a 1-30 day window. Recomputed straight from the
--   exposed timestamps, independent of the mart's days_to_next_admission column. This caught the
--   original bug: a plain `date_diff between 0 and 30` counted same-day transfers / overlapping
--   stays (52 false positives, inflating the rate to 13.50%).
--
--   Direction 2 (false negatives): an UNflagged index stay must have NO qualifying inpatient
--   admission in fct_encounters. Recomputed from fct_encounters directly, independent of the
--   mart's own next-admission lookup. This caught the second bug: the strictly-after fix used
--   lead() over admission order, so an overlapping stay "shadowed" a genuine later readmission
--   (14 false negatives, understating the rate as 7.29% when the correct figure is 8.96%).
--
--   Direction 3 (denominator): no index stay may belong to a patient who died on/before discharge —
--   they can never be readmitted, so counting them deflates the rate (standard 30-day readmission
--   measures exclude died-during-stay index admissions; 12 such rows = 8.96% vs the correct 9.09%).

with qualifying_next as (

    -- Earliest inpatient admission that starts strictly after each index stay's discharge and
    -- falls inside the 1-30 day window, straight from fct_encounters.
    select
        m.index_encounter_id,
        min(e.encounter_start) as first_qualifying_admission
    from {{ ref('mart_readmissions') }} m
    join {{ ref('fct_encounters') }} e
      on e.patient_id = m.patient_id
     and e.encounter_class = 'inpatient'
     and e.encounter_id <> m.index_encounter_id
     and e.encounter_start > m.discharge_date
     and date_diff('day', m.discharge_date, e.encounter_start) between 1 and 30
    group by m.index_encounter_id

)

-- Direction 1: flagged, but the exposed next admission does not satisfy the definition.
select
    m.index_encounter_id,
    m.patient_id,
    m.discharge_date,
    m.next_admission_start          as offending_admission_start,
    'flagged_without_qualifying_next' as failure_mode
from {{ ref('mart_readmissions') }} m
where m.is_30d_readmission
  and (
        m.next_admission_start is null
     or m.next_admission_start <= m.discharge_date
     or date_diff('day', m.discharge_date, m.next_admission_start) not between 1 and 30
  )

union all

-- Direction 2: not flagged, yet a qualifying readmission exists in fct_encounters.
select
    m.index_encounter_id,
    m.patient_id,
    m.discharge_date,
    q.first_qualifying_admission    as offending_admission_start,
    'missed_qualifying_readmission'  as failure_mode
from {{ ref('mart_readmissions') }} m
join qualifying_next q
  on q.index_encounter_id = m.index_encounter_id
where not m.is_30d_readmission

union all

-- Direction 3: the denominator must not contain stays the patient did not survive.
select
    m.index_encounter_id,
    m.patient_id,
    m.discharge_date,
    cast(p.death_date as timestamp) as offending_admission_start,
    'died_during_index_stay_in_denominator' as failure_mode
from {{ ref('mart_readmissions') }} m
join {{ ref('dim_patient') }} p using (patient_id)
where p.death_date is not null
  and p.death_date <= cast(m.discharge_date as date)
