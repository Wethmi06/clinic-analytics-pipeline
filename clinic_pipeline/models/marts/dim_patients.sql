-- dim_patients.sql
--
-- One row per real, deduplicated patient. Uses the canonical_patient_id
-- chosen by int_patient_dedup_bridge.sql -- the original, near-duplicate
-- raw_patient_id values are NOT included here as separate rows.

select distinct
    b.canonical_patient_id   as patient_id,
    p.district,
    p.age,
    p.gender,
    p.registration_date

from {{ ref('int_patient_dedup_bridge') }} b
inner join {{ ref('stg_patients') }} p
    on b.canonical_patient_id = p.patient_id