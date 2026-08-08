# Clinic Analytics Pipeline

An end-to-end data engineering and analytics project simulating a healthcare appointment management system for a fictional Sri Lanka clinic network.

Built to demonstrate a production-style data pipeline — from raw data extraction through transformation, orchestration, machine learning, and an interactive dashboard.

---

## What This Project Does

The pipeline ingests real reference data (ICD-10 diagnosis codes, clinic locations from OpenStreetMap), generates realistic synthetic appointment data with deliberate data quality issues, transforms it through a multi-layer dbt model, and serves insights through a Streamlit dashboard backed by a no-show prediction model.

**Business questions answered:**
- Which departments and clinics have the highest patient no-show rates?
- Which doctors carry the most risk in terms of volume and no-show rate?
- How many clinics are meeting the 30-minute wait-time SLA?
- Which upcoming appointments are most likely to result in a no-show?

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Airflow DAG (daily)                       │
│                                                              │
│  Extract       Generate        Load          Transform       │
│  ─────────     ──────────      ────────      ──────────      │
│  NLM API   →  Synthetic    →  PostgreSQL  →  dbt models  →  Dashboard
│  OSM API      patients &      (Docker)       staging →       Streamlit
│               appointments                   marts           + ML model
└─────────────────────────────────────────────────────────────┘
```

**Data flow:**
1. **Extract** — Real ICD-10-CM codes (NLM Clinical Tables API) and clinic locations (OpenStreetMap Overpass API) pulled as reference tables
2. **Generate** — Synthetic patients, appointments, and billing records with deliberate messiness (duplicate patients, missing diagnosis codes, duplicate rows)
3. **Load** — Raw CSVs loaded into PostgreSQL running in Docker as untyped text tables (ELT pattern)
4. **Transform** — dbt builds a star schema across 4 layers (staging → intermediate → dimensions/facts → marts) with 25 automated data quality tests
5. **Predict** — Random Forest classifier trained on historical appointments scores upcoming bookings by no-show risk
6. **Serve** — Streamlit dashboard with interactive filters, a department/day heatmap, SLA gauge, and geographic clinic map

---

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow 2.9 |
| Containerisation | Docker + Docker Compose |
| Storage | PostgreSQL 16 |
| Transformation | dbt-core 1.10 + dbt-postgres |
| Machine Learning | scikit-learn (Random Forest) |
| Dashboard | Streamlit + Plotly |
| Real data sources | NLM Clinical Tables API (ICD-10-CM), OpenStreetMap Overpass API |

---

## dbt Model Layers

```
models/
├── staging/          # Clean + type-cast raw tables (1:1 with sources)
│   ├── stg_appointments.sql
│   ├── stg_patients.sql
│   └── ...
├── intermediate/     # Business logic helpers
│   └── int_patient_dedup_bridge.sql   # Fuzzy patient deduplication
└── marts/
    ├── dim_patients.sql               # Deduplicated patient dimension
    ├── dim_doctors.sql
    ├── dim_clinics.sql                # Real OSM clinic locations
    ├── fact_appointments.sql          # Core fact table
    ├── fact_billing.sql
    ├── mart_no_show_summary.sql       # No-show rate by dept & month
    ├── mart_doctor_utilization.sql    # Workload + wait time per doctor
    └── mart_sla_performance.sql       # 30-min SLA compliance by clinic
```

**25 automated dbt tests** cover uniqueness, not-null constraints, referential integrity, and accepted value checks across all dimension and fact tables.

---

## Data Quality Story

The synthetic data generator deliberately injects:
- **~30 duplicate patients** — same person registered twice across different front-desk systems
- **~3% missing diagnosis codes** — simulating incomplete intake forms
- **~1% duplicate appointment rows** — simulating a pipeline glitch

The `int_patient_dedup_bridge` model resolves patient duplicates using a composite key match (same district + gender + registration date + age ±1), achieving **30/30 recall** against a known answer key with zero false positives.

---

## No-Show Prediction Model

A Random Forest classifier trained on 2,191 historical appointments predicts no-show probability for upcoming bookings.

**Features used:**
- Lead time (days between booking and appointment)
- Day of week and month
- Patient age
- Department
- Patient's past no-show count

**Results:** AUC 0.60 on a held-out test set. Top predictors: patient age and lead time — consistent with the patterns built into the data generator.

**Output:** `dbt_dev.mart_no_show_predictions` table with risk labels (High / Medium / Low) queryable by the dashboard.

---

## Dashboard Pages

| Page | What it shows |
|---|---|
| Overview | KPIs with month-on-month trends, no-show rate over time, dynamic Key Findings panel |
| No-Show Analysis | Department filters, day-of-week bar chart, department × day heatmap |
| Doctor Workload | Bubble chart of workload vs no-show rate, sortable doctor table |
| SLA & Wait Times | SLA compliance gauge, per-clinic bar chart, geographic map of real clinic locations |
| No-Show Risk Prediction | Risk distribution histogram, department breakdown, high-risk appointment table |

---

## Project Structure

```
clinic-analytics-pipeline/
├── airflow_dags/
│   └── clinic_pipeline_dag.py     # Daily orchestration DAG
├── clinic_pipeline/               # dbt project
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   └── dbt_project.yml
├── dashboard/
│   └── dashboard.py               # Streamlit app
├── scripts/
│   ├── extract_reference_data.py  # ICD-10 + OSM extraction
│   ├── generate_synthetic_data.py # Synthetic data generator
│   ├── load_to_postgres.py        # CSV → PostgreSQL loader
│   └── train_noshow_model.py      # Random Forest training + scoring
├── docker-compose.yml             # PostgreSQL + Airflow services
└── README.md
```

---

## Running Locally

### Prerequisites
- Docker Desktop
- Python 3.13+
- Git

### Setup

```bash
# Clone the repo
git clone https://github.com/Wethmi06/clinic-analytics-pipeline.git
cd clinic-analytics-pipeline

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install dbt-postgres==1.10.* psycopg2-binary requests \
            scikit-learn pandas sqlalchemy streamlit plotly
```

### Run the pipeline

```bash
# Start PostgreSQL + Airflow
docker compose up -d

# Extract real reference data
python scripts/extract_reference_data.py

# Generate synthetic data
python scripts/generate_synthetic_data.py

# Load to PostgreSQL
python scripts/load_to_postgres.py

# Run dbt transformations
cd clinic_pipeline
dbt run
dbt test

# Train no-show model
cd ..
python scripts/train_noshow_model.py

# Launch dashboard
streamlit run dashboard/dashboard.py
```

Open `http://localhost:8501` for the dashboard and `http://localhost:8081` for the Airflow UI (login: admin / admin).

---

## Key Design Decisions

**Why synthetic data?** Real patient records are protected under healthcare privacy regulations. Synthetic data generated with realistic distributions is the industry-standard approach for analytics engineering portfolios and testing environments.

**Why ELT over ETL?** Raw data is loaded first as untyped text, then transformed inside the warehouse using dbt. This preserves the original data for debugging and lets the transformation logic live in version-controlled SQL rather than scattered ingestion scripts.

**Why a Random Forest over a simpler model?** Random Forest handles the mix of numeric and categorical features without scaling, is naturally resistant to overfitting on a dataset this size, and provides interpretable feature importances — useful for explaining which factors drive no-show risk.

