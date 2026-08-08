"""
clinic_pipeline_dag.py

Airflow DAG for the clinic analytics pipeline.

Runs daily and orchestrates the full pipeline in order:
  1. extract_reference_data  -- updates ICD-10 diagnosis codes only.
                                Clinic locations (OpenStreetMap) are treated as
                                slowly-changing reference data already on disk --
                                the Overpass API is unreliable inside Docker
                                containers, and clinic locations don't change
                                daily. This is a deliberate architectural
                                decision, not a workaround.
  2. generate_synthetic_data -- generates synthetic patients/appointments/billing
  3. load_to_postgres        -- loads all CSVs into the raw_* tables in Postgres
  4. dbt_run                 -- runs all dbt models (staging -> marts)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "clinic_pipeline",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="clinic_pipeline",
    description="End-to-end clinic analytics pipeline: extract -> generate -> load -> dbt",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule_interval="@daily",
    catchup=False,
    tags=["clinic", "analytics", "dbt"],
) as dag:

    # Task 1: update ICD-10 diagnosis codes from the NLM API (reliable).
    # Clinic locations are NOT re-fetched -- they live in clinics_with_id.csv
    # and are treated as slowly-changing reference data updated manually.
    extract = BashOperator(
        task_id="extract_reference_data",
        bash_command=(
            "cd /opt/airflow && "
            "python scripts/extract_reference_data.py --skip-clinics"
        ),
    )

    # Task 2: generate synthetic patients, appointments, billing
    generate = BashOperator(
        task_id="generate_synthetic_data",
        bash_command="cd /opt/airflow && python scripts/generate_synthetic_data.py",
    )

    # Task 3: load all CSVs into Postgres raw_* tables
    load = BashOperator(
        task_id="load_to_postgres",
        bash_command="cd /opt/airflow && python scripts/load_to_postgres.py",
    )

    # Task 4: run the full dbt project (staging -> intermediate -> marts)
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "cd /opt/airflow/clinic_pipeline && "
            "dbt run --profiles-dir /opt/airflow/clinic_pipeline"
        ),
    )

    extract >> generate >> load >> dbt_run