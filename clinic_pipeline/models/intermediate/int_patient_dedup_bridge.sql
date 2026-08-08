-- int_patient_dedup_bridge.sql
--
-- Intermediate model: NOT a dimension or fact, just a mapping table.
--
-- Problem: ~5% of patients in stg_patients are accidental duplicates of a
-- real person (same person registered twice under a different
-- source_system -- see generate_synthetic_data.py). There's no name field
-- to match on (privacy by design), so we approximate real-world entity
-- resolution using: same district + same gender + same registration_date
-- + age within 1 year. The exact registration_date match matters a lot --
-- an earlier version of this model matched on district + gender + age
-- alone and flagged 127 patients as duplicates (vs. the ~30 actually
-- injected), because those three fields alone collide by chance fairly
-- often across 600 patients spread over only 25 districts. Adding the
-- registration_date requirement (which the generator always copies
-- exactly for true duplicates, while genuinely different people are very
-- unlikely to share the same registration day) sharply cuts down those
-- false-positive merges.
--
-- Known limitation (worth stating plainly, not hiding): this uses a
-- pairwise match rather than full transitive grouping. If patient A
-- matches B, and B matches C, but A and C don't directly match each other,
-- A and C will NOT be merged into the same group. For this dataset's
-- duplicate rate, that scenario is rare, but it's a real simplification
-- worth being able to explain rather than one to gloss over.

with candidate_matches as (

    -- For every patient, find every OTHER patient who could plausibly be
    -- the same person: same district, same gender, age within 1 year.
    select
        p1.patient_id                  as patient_id,
        p1.registration_date           as patient_registration_date,
        p2.patient_id                  as match_patient_id,
        p2.registration_date           as match_registration_date

    from {{ ref('stg_patients') }} p1
    inner join {{ ref('stg_patients') }} p2
        on p1.district = p2.district
        and p1.gender = p2.gender
        and p1.registration_date = p2.registration_date
        and abs(p1.age - p2.age) <= 1

),

canonical_per_patient as (

    -- For each patient, the canonical match is whichever record in their
    -- candidate group (including themselves) registered earliest. Ties
    -- broken by patient_id for a deterministic result.
    select
        patient_id,
        first_value(match_patient_id) over (
            partition by patient_id
            order by match_registration_date asc, match_patient_id asc
        ) as canonical_patient_id

    from candidate_matches

)

select distinct
    c.patient_id              as raw_patient_id,
    c.canonical_patient_id,
    (c.patient_id != c.canonical_patient_id) as is_likely_duplicate

from canonical_per_patient c