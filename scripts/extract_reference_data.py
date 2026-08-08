"""
extract_reference_data.py

Day 2 of the clinic analytics pipeline project.

Pulls two REAL reference datasets and saves them as CSVs:
  1. Diagnosis codes (ICD-10-CM) via the NLM Clinical Table Search Service
     -> free, no signup, no API key required
  2. Clinic / hospital locations in Sri Lanka via the OpenStreetMap Overpass API
     -> free, no signup, no API key required

Output files:
  data/raw/diagnosis_codes.csv
  data/raw/clinics.csv

These become the real DIAGNOSIS_CODES and CLINICS dimension tables in your
star schema. Your synthetic data generator (Day 3) will pick from these
files instead of inventing fake diagnosis codes or fake clinic names.

Setup:
  pip install requests
"""

import csv
import os
import time
import requests

OUTPUT_DIR = "data/raw"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Diagnosis codes — NLM Clinical Table Search Service (ICD-10-CM)
# ---------------------------------------------------------------------------
ICD10_BASE_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"

# A realistic, focused list of diagnoses a general outpatient clinic would
# actually see day to day. Each search term below returns the best-matching
# real ICD-10-CM code(s). Expand this list any time.
DIAGNOSIS_SEARCH_TERMS = [
    "type 2 diabetes",
    "hypertension",
    "upper respiratory infection",
    "asthma",
    "migraine",
    "urinary tract infection",
    "anxiety disorder",
    "gastroenteritis",
    "osteoarthritis",
    "anemia",
    "hyperlipidemia",
    "depression",
    "allergic rhinitis",
    "back pain",
    "skin infection",
]


def fetch_icd10_codes(search_terms):
    """Query the NLM Clinical Table Search Service once per search term and
    return a deduplicated list of (code, description) tuples.

    The API response shape looks like:
      [ total_count, [codes...], extra_data, [[code, name], [code, name], ...] ]
    so payload[3] is the part we actually want.
    """
    results = {}
    for term in search_terms:
        params = {
            "sf": "code,name",  # which fields to search against
            "terms": term,
            "maxList": 3,       # take the top few matches per search term
        }
        response = requests.get(ICD10_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        code_name_pairs = payload[3]
        for code, name in code_name_pairs:
            results[code] = name
        time.sleep(0.2)  # be polite to the free public API
    return [(code, name) for code, name in results.items()]


# ---------------------------------------------------------------------------
# 2. Clinic / hospital locations — OpenStreetMap Overpass API
# ---------------------------------------------------------------------------
# Try the main server first, then fall back to a community mirror if it's
# rejecting requests (Overpass's main server has gotten stricter about
# bot-like traffic — a backup endpoint makes this script more reliable).
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Overpass requires a real, identifiable User-Agent these days, or it will
# reject the request with a 406 error. Replace the email with your own.
OVERPASS_HEADERS = {
    "User-Agent": "clinic-analytics-pipeline/1.0 (student portfolio project; contact: your-email@example.com)",
    "Accept": "application/json",
}

# Overpass QL query: find every node tagged as a clinic or hospital
# inside a bounding box around Sri Lanka (min_lat, min_lon, max_lat, max_lon).
# A plain bounding box is much cheaper for the server than resolving the
# full administrative boundary polygon for a country — that lookup is what
# was causing the 504 Gateway Timeout.
SRI_LANKA_BBOX = "5.9,79.5,9.9,82.0"  # roughly covers the whole island

OVERPASS_QUERY = f"""
[out:json][timeout:90];
(
  node["amenity"="clinic"]({SRI_LANKA_BBOX});
  node["amenity"="hospital"]({SRI_LANKA_BBOX});
);
out body;
"""


def fetch_sri_lanka_clinics():
    """Query Overpass for clinic/hospital nodes in Sri Lanka and return a
    list of dicts with name, district (if tagged), latitude, longitude.

    Tries each URL in OVERPASS_URLS in order, since the main Overpass
    server occasionally rejects, rate-limits, or times out on requests.
    """
    response = None
    last_error = None
    for url in OVERPASS_URLS:
        try:
            response = requests.post(
                url,
                data={"data": OVERPASS_QUERY},
                headers=OVERPASS_HEADERS,
                timeout=120,
            )
            response.raise_for_status()
            break  # success — stop trying other URLs
        except requests.exceptions.RequestException as e:
            print(f"  {url} failed ({e}), trying next option...")
            last_error = e
            response = None

    if response is None:
        raise RuntimeError(
            "All Overpass endpoints failed. This is usually a temporary "
            "server overload — wait a few minutes and run the script again, "
            "or check https://overpass-api.de/api/status"
        ) from last_error

    elements = response.json().get("elements", [])

    clinics = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue  # skip unnamed nodes — not useful for a dimension table
        clinics.append({
            "name": name,
            "district": tags.get("addr:district") or tags.get("addr:city", "Unknown"),
            "latitude": el.get("lat"),
            "longitude": el.get("lon"),
        })
    return clinics


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------
def save_diagnosis_codes(pairs, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["icd10_code", "description"])
        writer.writerows(sorted(pairs))
    print(f"Saved {len(pairs)} diagnosis codes -> {path}")


def save_clinics(clinics, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "district", "latitude", "longitude"])
        writer.writeheader()
        writer.writerows(clinics)
    print(f"Saved {len(clinics)} clinics -> {path}")


if __name__ == "__main__":
    import sys
    skip_clinics = "--skip-clinics" in sys.argv

    print("Fetching diagnosis codes from NLM Clinical Table Search Service...")
    diagnosis_pairs = fetch_icd10_codes(DIAGNOSIS_SEARCH_TERMS)
    save_diagnosis_codes(diagnosis_pairs, os.path.join(OUTPUT_DIR, "diagnosis_codes.csv"))

    clinics_path = os.path.join(OUTPUT_DIR, "clinics.csv")

    if skip_clinics:
        if os.path.exists(clinics_path):
            print(f"Skipping Overpass fetch (--skip-clinics). Reusing existing {clinics_path}.")
        else:
            raise RuntimeError(
                "--skip-clinics passed but no clinics.csv found. "
                "Run the script manually once without --skip-clinics to create it."
            )
    else:
        print("Fetching clinic/hospital locations from OpenStreetMap Overpass API...")
        try:
            clinics = fetch_sri_lanka_clinics()
            save_clinics(clinics, clinics_path)
        except Exception as e:
            if os.path.exists(clinics_path):
                print(f"Overpass API failed ({e}). Reusing existing {clinics_path}.")
            else:
                raise RuntimeError(
                    f"Overpass API failed and no existing clinics.csv found. "
                    f"Run the extraction script manually first to create {clinics_path}."
                ) from e

    print("Extraction complete.")