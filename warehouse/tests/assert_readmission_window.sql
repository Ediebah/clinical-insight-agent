-- Singular test guarding the 30-day readmission window (mart_readmissions.is_30d_readmission).
-- A flagged readmission MUST have its next inpatient admission start STRICTLY AFTER discharge and
-- land within a 1-30 day window. This recomputes the gap straight from the exposed timestamps
-- (independent of the mart's days_to_next_admission column), so it fails if the flag ever diverges
-- from its own definition. dbt singular tests fail when the query returns any rows.
--
-- This would have caught the pre-fix bug: the old flag used date_diff('day', ...) between 0 and 30,
-- which counted same-day transfers / overlapping stays whose next admission starts before discharge
-- (elapsed time negative, calendar-day diff 0). Against the full dataset that mis-flagged 52 rows,
-- inflating the readmission rate from the correct 7.29% to 13.50%.

select
    index_encounter_id,
    patient_id,
    discharge_date,
    next_admission_start,
    date_diff('day', discharge_date, next_admission_start) as days_gap
from {{ ref('mart_readmissions') }}
where is_30d_readmission
  and (
        next_admission_start is null                                              -- flagged w/ no next stay
     or next_admission_start <= discharge_date                                    -- starts at/before discharge
     or date_diff('day', discharge_date, next_admission_start) not between 1 and 30  -- outside 1-30 day window
  )
