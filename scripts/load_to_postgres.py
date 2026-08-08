"""
load_to_postgres.py

Day 4 of the clinic analytics pipeline project.

Loads all six raw CSVs (from Day 2 + Day 3) into the local Postgres
container as "raw" tables. Every column is loaded as TEXT on purpose --
this is the classic ELT "raw landing zone" pattern: load first, clean
and type-cast later inside dbt. Forcing strict types at load time is
exactly what breaks on messy real-world data (a blank wait_time_minutes,
a missing icd10_code) -- and this dataset has intentional messiness, so
that distinction matters here.

Requires the Postgres container to already be running:
    docker compose up -d

Install dependency:
    pip install psycopg2-binary

Safe to re-run: it drops and recreates each raw_* table every time, so
re-running this script after regenerating your CSVs just refreshes
the data.
"""

import os
import psycopg2

DB_CONFIG = {
    "host": os.environ.get("CLINIC_DB_HOST", "localhost"),
    "port": int(os.environ.get("CLINIC_DB_PORT", 5432)),
    "dbname": os.environ.get("CLINIC_DB_NAME", "clinic_db"),
    "user": os.environ.get("CLINIC_DB_USER", "clinic_user"),
    "password": os.environ.get("CLINIC_DB_PASS", "clinic_pass"),
}

RAW_DIR = "data/raw"

# table_name -> (csv_filename, [column names, same order as the CSV header])
TABLES = {
    "raw_clinics": (
        "clinics_with_id.csv",
        ["clinic_id", "name", "district", "latitude", "longitude"],
    ),
    "raw_diagnosis_codes": (
        "diagnosis_codes.csv",
        ["icd10_code", "description"],
    ),
    "raw_departments": (
        "departments.csv",
        ["department_id", "department_name"],
    ),
    "raw_doctors": (
        "doctors.csv",
        ["doctor_id", "name", "department_id", "clinic_id", "years_experience"],
    ),
    "raw_patients": (
        "patients.csv",
        ["patient_id", "source_system", "district", "age", "gender", "registration_date"],
    ),
    "raw_appointments": (
        "appointments.csv",
        ["appointment_id", "patient_id", "doctor_id", "clinic_id", "department_id",
         "icd10_code", "booking_date", "scheduled_date", "lead_time_days",
         "status", "wait_time_minutes"],
    ),
    "raw_billing": (
        "billing.csv",
        ["billing_id", "appointment_id", "amount", "payment_status", "insurance_provider"],
    ),
}


def create_tables(cur):
    for table_name, (_, columns) in TABLES.items():
        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
        column_defs = ", ".join(f"{col} TEXT" for col in columns)
        cur.execute(f"CREATE TABLE {table_name} ({column_defs});")
    print("Created all raw_* tables (dropped + recreated -- safe to re-run).")


def load_table(cur, table_name, csv_filename):
    path = os.path.join(RAW_DIR, csv_filename)
    with open(path, "r", encoding="utf-8") as f:
        # COPY is Postgres's bulk-load command -- it streams the whole file
        # straight into the table, far faster than inserting row by row.
        cur.copy_expert(f"COPY {table_name} FROM STDIN WITH CSV HEADER", f)


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            create_tables(cur)
            for table_name, (csv_filename, _) in TABLES.items():
                load_table(cur, table_name, csv_filename)
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cur.fetchone()[0]
                print(f"Loaded {count} rows -> {table_name}")
        conn.commit()
        print("Day 4 load complete -- all raw tables are in Postgres.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()