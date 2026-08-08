"""
generate_synthetic_data.py

Day 3 of the clinic analytics pipeline project.

Generates synthetic clinic data that REFERENCES the two real datasets
pulled in Day 2 (real diagnosis codes, real clinic locations), and
deliberately includes realistic messiness (duplicate patient records,
missing fields, duplicate rows) so there's something genuine to clean
up later with dbt.

Reads:
  data/raw/clinics.csv          (real, from Day 2)
  data/raw/diagnosis_codes.csv  (real, from Day 2)

Writes (all synthetic):
  data/raw/clinics_with_id.csv   (the same real clinics, with an added clinic_id)
  data/raw/departments.csv
  data/raw/doctors.csv
  data/raw/patients.csv          (includes intentional near-duplicate patients)
  data/raw/appointments.csv      (includes some missing/duplicate rows)
  data/raw/billing.csv
  data/raw/_duplicate_patients_answer_key.csv
      -> NOT part of the pipeline. Just for you to check later how many
         of these duplicates your dbt dedup logic actually catches.

No new dependencies — everything here uses Python's standard library.
"""

import csv
import os
import random
import uuid
from datetime import date, timedelta

random.seed(42)  # same "random" data every time you run this, for consistency

RAW_DIR = "data/raw"

# ---------------------------------------------------------------------------
# Reference lists — Sri Lanka districts, fictional doctor names
# ---------------------------------------------------------------------------
DISTRICTS = [
    "Colombo", "Gampaha", "Kalutara", "Kandy", "Matale", "Nuwara Eliya",
    "Galle", "Matara", "Hambantota", "Jaffna", "Kilinochchi", "Mannar",
    "Vavuniya", "Mullaitivu", "Batticaloa", "Ampara", "Trincomalee",
    "Kurunegala", "Puttalam", "Anuradhapura", "Polonnaruwa", "Badulla",
    "Monaragala", "Ratnapura", "Kegalle",
]

FIRST_NAMES = [
    "Nimal", "Sunil", "Kumari", "Anoma", "Priyantha", "Chamari", "Ruwan",
    "Dilani", "Saman", "Anusha", "Kasun", "Nilmini", "Roshan", "Tharindu",
    "Sachini",
]
SURNAMES = [
    "Perera", "Silva", "Fernando", "Jayawardena", "Rajapakse",
    "Wickramasinghe", "Bandara", "Gunawardena", "Senanayake", "Dissanayake",
]

# Department -> which real ICD-10 codes (from Day 2) belong to it.
# Hand-picked to be common, general-practice-style diagnoses rather than
# the rarer codes that also showed up in the Day 2 search results.
DEPARTMENT_DIAGNOSES = {
    "General Medicine": ["A09", "N39.0", "I15.0", "D64.9"],
    "Endocrinology": ["E11.9", "E78.5"],
    "Respiratory Medicine": ["J06.9", "J45.909", "J30.9"],
    "Orthopedics": ["M54.50", "M16.9"],
    "Psychiatry": ["F41.9", "F32.A"],
    "Gastroenterology": ["K52.1"],
}

DEPARTMENT_BASE_FEE = {
    "General Medicine": 1500,
    "Endocrinology": 2500,
    "Respiratory Medicine": 2200,
    "Orthopedics": 3000,
    "Psychiatry": 3500,
    "Gastroenterology": 2800,
}

NUM_PATIENTS = 600
NUM_DOCTORS = 18
DUPLICATE_PATIENT_RATE = 0.05    # ~5% of patients get accidentally re-registered
MIN_APPTS_PER_PATIENT = 1
MAX_APPTS_PER_PATIENT = 10
MISSING_DIAGNOSIS_RATE = 0.03    # ~3% of appointments missing icd10_code
DUPLICATE_APPT_RATE = 0.01       # ~1% of appointments accidentally duplicated
SOURCE_SYSTEMS = ["FrontDeskA", "FrontDeskB", "OnlinePortal"]
TODAY = date.today()


# ---------------------------------------------------------------------------
# Load the real reference data from Day 2
# ---------------------------------------------------------------------------
def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_clinics():
    """Load the real clinics from Day 2 and assign each a simple clinic_id
    (the real file has no ID column). Writes clinics_with_id.csv so later
    steps (dbt, the dashboard) have something to join against — the
    original clinics.csv from Day 2 is left untouched.
    """
    clinics = load_csv(os.path.join(RAW_DIR, "clinics.csv"))
    for i, clinic in enumerate(clinics, start=1):
        clinic["clinic_id"] = f"CLN-{i:04d}"

    out_path = os.path.join(RAW_DIR, "clinics_with_id.csv")
    save_csv(clinics, out_path, ["clinic_id", "name", "district", "latitude", "longitude"])
    print(f"Loaded {len(clinics)} real clinics -> {out_path}")
    return clinics


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------
def generate_departments():
    return [
        {"department_id": f"DEPT-{i + 1:02d}", "department_name": name}
        for i, name in enumerate(DEPARTMENT_DIAGNOSES.keys())
    ]


# ---------------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------------
def generate_doctors(departments, clinics, num_doctors=NUM_DOCTORS):
    doctors = []
    for i in range(1, num_doctors + 1):
        dept = random.choice(departments)
        clinic = random.choice(clinics)
        name = f"Dr. {random.choice(FIRST_NAMES)} {random.choice(SURNAMES)}"
        doctors.append({
            "doctor_id": f"DOC-{i:03d}",
            "name": name,
            "department_id": dept["department_id"],
            "clinic_id": clinic["clinic_id"],
            "years_experience": random.randint(1, 30),
        })
    return doctors


# ---------------------------------------------------------------------------
# Patients (no names stored — privacy by design)
# ---------------------------------------------------------------------------
def generate_patients(num_patients=NUM_PATIENTS):
    patients = []
    for _ in range(num_patients):
        reg_date = TODAY - timedelta(days=random.randint(30, 730))
        patients.append({
            "patient_id": str(uuid.uuid4()),
            "source_system": random.choice(SOURCE_SYSTEMS),
            "district": random.choice(DISTRICTS),
            "age": random.randint(1, 90),
            "gender": random.choice(["F", "M"]),
            "registration_date": reg_date.isoformat(),
        })
    return patients


def inject_duplicate_patients(patients):
    """Simulate the same real person accidentally being registered twice —
    e.g. a different front desk didn't recognise them. Slightly varies the
    recorded details, like a real re-entry would, rather than being an
    exact copy.

    Also writes a small "answer key" file (NOT used anywhere downstream in
    the pipeline) so you can check later how many of these your dbt dedup
    logic actually catches.
    """
    answer_key = []
    num_duplicates = int(len(patients) * DUPLICATE_PATIENT_RATE)
    originals = random.sample(patients, num_duplicates)

    for original in originals:
        duplicate = dict(original)
        duplicate["patient_id"] = str(uuid.uuid4())
        other_systems = [s for s in SOURCE_SYSTEMS if s != original["source_system"]]
        duplicate["source_system"] = random.choice(other_systems)
        duplicate["age"] = original["age"] + random.choice([-1, 0, 0, 1])
        patients.append(duplicate)
        answer_key.append({
            "patient_id_a": original["patient_id"],
            "patient_id_b": duplicate["patient_id"],
        })

    out_path = os.path.join(RAW_DIR, "_duplicate_patients_answer_key.csv")
    save_csv(answer_key, out_path, ["patient_id_a", "patient_id_b"])
    print(f"Injected {num_duplicates} duplicate patient records (answer key -> {out_path})")
    return patients


# ---------------------------------------------------------------------------
# Appointments + the no-show outcome model
# ---------------------------------------------------------------------------
def no_show_probability(lead_time_days, weekday, age, past_no_show_count):
    """A simple hand-built rule for how likely an appointment is to be a
    no-show. This is the 'ground truth' pattern your Day 9 ML model will
    later try to learn back out from the data — the model never sees this
    function, only the resulting outcomes.
    """
    prob = 0.15
    prob += min(lead_time_days * 0.01, 0.25)   # longer lead time -> more risk
    if weekday == 0:                            # Monday
        prob += 0.05
    if age < 30:
        prob += 0.05
    elif age > 55:
        prob -= 0.10
    prob += min(past_no_show_count * 0.03, 0.30)
    return max(0.02, min(prob, 0.85))


def generate_appointments(patients, doctors, departments):
    dept_by_id = {d["department_id"]: d for d in departments}
    appointments = []
    patient_no_show_counts = {p["patient_id"]: 0 for p in patients}

    for patient in patients:
        num_appts = random.randint(MIN_APPTS_PER_PATIENT, MAX_APPTS_PER_PATIENT)
        # Spread this patient's appointments across roughly the last 18
        # months, moving forward in time, so "past no-show count" builds
        # up the way it would for a real patient.
        current_date = TODAY - timedelta(days=random.randint(60, 540))

        for _ in range(num_appts):
            doctor = random.choice(doctors)
            department = dept_by_id[doctor["department_id"]]
            diagnosis_pool = DEPARTMENT_DIAGNOSES[department["department_name"]]
            icd10_code = random.choice(diagnosis_pool)

            lead_time_days = random.choice([0, 1, 2, 3, 5, 7, 10, 14, 21, 30])
            booking_date = current_date - timedelta(days=lead_time_days)
            scheduled_date = current_date
            past_count = patient_no_show_counts[patient["patient_id"]]

            if scheduled_date > TODAY:
                # Hasn't happened yet — exactly the kind of row your
                # no-show model will be asked to score later.
                status = "scheduled"
                wait_time_minutes = ""
            elif random.random() < 0.04:
                status = "cancelled"
                wait_time_minutes = ""
            else:
                prob = no_show_probability(
                    lead_time_days, scheduled_date.weekday(),
                    patient["age"], past_count,
                )
                if random.random() < prob:
                    status = "no_show"
                    wait_time_minutes = ""
                    patient_no_show_counts[patient["patient_id"]] += 1
                else:
                    status = "attended"
                    wait_time_minutes = random.randint(5, 90)

            # Intentional messiness: occasionally drop the diagnosis code
            if random.random() < MISSING_DIAGNOSIS_RATE:
                icd10_code = ""

            appointments.append({
                "appointment_id": str(uuid.uuid4()),
                "patient_id": patient["patient_id"],
                "doctor_id": doctor["doctor_id"],
                "clinic_id": doctor["clinic_id"],
                "department_id": department["department_id"],
                "icd10_code": icd10_code,
                "booking_date": booking_date.isoformat(),
                "scheduled_date": scheduled_date.isoformat(),
                "lead_time_days": lead_time_days,
                "status": status,
                "wait_time_minutes": wait_time_minutes,
            })

            current_date = current_date + timedelta(days=random.randint(20, 120))
            if current_date > TODAY + timedelta(days=30):
                break

    # Intentional messiness: a few exact-duplicate rows, like a pipeline
    # glitch that re-inserted the same appointment twice.
    num_dupes = int(len(appointments) * DUPLICATE_APPT_RATE)
    appointments.extend(random.sample(appointments, num_dupes))

    random.shuffle(appointments)
    return appointments


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------
def generate_billing(appointments, departments):
    dept_by_id = {d["department_id"]: d for d in departments}
    billing = []
    for appt in appointments:
        if appt["status"] not in ("attended", "no_show"):
            continue  # no bill for cancelled or not-yet-happened appointments

        dept_name = dept_by_id[appt["department_id"]]["department_name"]
        base_fee = DEPARTMENT_BASE_FEE[dept_name]
        if appt["status"] == "no_show":
            amount = int(base_fee * 0.2)  # smaller no-show fee, not a full visit
        else:
            amount = base_fee + random.randint(-200, 500)

        billing.append({
            "billing_id": str(uuid.uuid4()),
            "appointment_id": appt["appointment_id"],
            "amount": amount,
            "payment_status": random.choice(["paid", "pending", "insurance_pending"]),
            "insurance_provider": random.choice(["None", "SLIC", "Ceylinco", "AIA"]),
        })
    return billing


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------
def save_csv(rows, path, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    clinics = load_clinics()
    departments = generate_departments()
    doctors = generate_doctors(departments, clinics)
    patients = generate_patients()
    patients = inject_duplicate_patients(patients)
    appointments = generate_appointments(patients, doctors, departments)
    billing = generate_billing(appointments, departments)

    save_csv(departments, os.path.join(RAW_DIR, "departments.csv"),
              ["department_id", "department_name"])
    print(f"Saved {len(departments)} departments -> data/raw/departments.csv")

    save_csv(doctors, os.path.join(RAW_DIR, "doctors.csv"),
              ["doctor_id", "name", "department_id", "clinic_id", "years_experience"])
    print(f"Saved {len(doctors)} doctors -> data/raw/doctors.csv")

    save_csv(patients, os.path.join(RAW_DIR, "patients.csv"),
              ["patient_id", "source_system", "district", "age", "gender", "registration_date"])
    print(f"Saved {len(patients)} patients (incl. duplicates) -> data/raw/patients.csv")

    save_csv(appointments, os.path.join(RAW_DIR, "appointments.csv"),
              ["appointment_id", "patient_id", "doctor_id", "clinic_id", "department_id",
               "icd10_code", "booking_date", "scheduled_date", "lead_time_days",
               "status", "wait_time_minutes"])
    print(f"Saved {len(appointments)} appointments -> data/raw/appointments.csv")

    save_csv(billing, os.path.join(RAW_DIR, "billing.csv"),
              ["billing_id", "appointment_id", "amount", "payment_status", "insurance_provider"])
    print(f"Saved {len(billing)} billing records -> data/raw/billing.csv")

    print("Day 3 generation complete.")