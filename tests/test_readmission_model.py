"""Regression tests for the actual dbt readmission model SQL."""
from pathlib import Path

import duckdb

MODEL = Path(__file__).resolve().parents[1] / "warehouse/models/marts/analytics/mart_readmissions.sql"


def test_same_day_return_does_not_hide_later_readmission():
    db = duckdb.connect()
    db.execute("""create table fct_encounters (
        encounter_id varchar, patient_id varchar, encounter_start timestamp,
        encounter_stop timestamp, total_claim_cost double, encounter_class varchar
    )""")
    db.execute("create table dim_patient (patient_id varchar, death_date date)")
    db.execute("insert into dim_patient values ('p', null)")
    db.execute("""insert into fct_encounters values
        ('index', 'p', '2024-01-01 10:00:00', '2024-01-02 10:00:00', 100, 'inpatient'),
        ('same-day', 'p', '2024-01-02 12:00:00', '2024-01-03 12:00:00', 100, 'inpatient'),
        ('later', 'p', '2024-01-23 08:00:00', '2024-01-24 08:00:00', 100, 'inpatient')
    """)
    sql = MODEL.read_text().replace("{{ ref('fct_encounters') }}", "fct_encounters")
    sql = sql.replace("{{ ref('dim_patient') }}", "dim_patient")
    result = db.execute(f"select next_admission_start, days_to_next_admission, is_30d_readmission "
                        f"from ({sql}) where index_encounter_id='index'").fetchone()
    assert str(result[0]) == "2024-01-23 08:00:00"
    assert result[1:] == (21, True)
    db.execute("delete from fct_encounters where encounter_id='later'")
    result = db.execute(f"select next_admission_start, days_to_next_admission, is_30d_readmission "
                        f"from ({sql}) where index_encounter_id='index'").fetchone()
    assert result == (None, None, False)
