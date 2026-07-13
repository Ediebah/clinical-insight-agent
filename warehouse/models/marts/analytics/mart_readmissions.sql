-- mart_readmissions — 30-day inpatient readmission flags.
-- Grain: one row per INDEX inpatient encounter the patient SURVIVED to discharge. PK: index_encounter_id.
-- Definition: an index inpatient stay is "readmitted" if the SAME patient has a subsequent inpatient
-- admission that starts STRICTLY AFTER this stay's discharge AND within a 1-30 day window.
-- Denominator: stays where the patient died on/before discharge are excluded (standard for 30-day
-- readmission measures — a patient who died in hospital can never be readmitted, so counting the
-- stay deflates the rate). Terminal stays still COUNT as readmissions of an earlier index stay.
-- Why the strictly-after guard: encounter_start/stop are TIMESTAMPs and date_diff('day', ...) counts
-- calendar-day boundaries crossed, NOT signed elapsed time. A plain `between 0 and 30` therefore
-- mis-counts same-day transfers and overlapping/nested stays whose next admission actually starts
-- BEFORE discharge (elapsed time negative, but date_diff('day', ...) reads 0).
-- Why min() over qualifying admissions and NOT lead() over admission order: lead() only sees the
-- single next admission, so an overlapping/nested stay sitting between the index stay and a genuine
-- later readmission "shadows" it and the flag reads false. Against the seeded dataset lead() missed
-- 14 real readmissions (rate 7.29% instead of the correct 8.96%). The earliest admission that starts
-- strictly after discharge is the readmission candidate, wherever it falls in admission order.

with inpatient as (
    select
        encounter_id,
        patient_id,
        encounter_start,
        encounter_stop,
        total_claim_cost
    from {{ ref('fct_encounters') }}
    where encounter_class = 'inpatient'
),

-- Only SURVIVED-to-discharge stays are index stays (the denominator). The exclusion must NOT apply
-- to the candidate next admissions below: a readmission the patient died during is still a
-- readmission of its index stay.
index_stays as (
    select i.*
    from inpatient i
    join {{ ref('dim_patient') }} p using (patient_id)
    where p.death_date is null
       or p.death_date > cast(i.encounter_stop as date)
),

next_post_discharge as (
    select
        i.encounter_id,
        min(n.encounter_start) as next_admission_start
    from index_stays i
    join inpatient n
      on n.patient_id = i.patient_id
     and n.encounter_id <> i.encounter_id
     and n.encounter_start > i.encounter_stop
    group by i.encounter_id
)

select
    i.encounter_id                                              as index_encounter_id,
    i.patient_id,
    i.encounter_start                                           as admission_date,
    i.encounter_stop                                            as discharge_date,
    n.next_admission_start,
    -- days from discharge to the earliest strictly-post-discharge admission; null when the patient
    -- has no later inpatient admission at all. Overlapping/concurrent stays never appear here.
    date_diff('day', i.encounter_stop, n.next_admission_start)  as days_to_next_admission,
    -- Readmission = that earliest post-discharge admission lands within a 1-30 day window
    -- (day 0 excluded: a same-calendar-day return is indistinguishable from a transfer here).
    coalesce(
        date_diff('day', i.encounter_stop, n.next_admission_start) between 1 and 30,
        false
    )                                                           as is_30d_readmission,
    i.total_claim_cost
from index_stays i
left join next_post_discharge n
  on n.encounter_id = i.encounter_id
