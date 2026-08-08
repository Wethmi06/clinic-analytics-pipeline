-- stg_patients.sql
--
-- Cleans the raw patients table.
-- This table intentionally contains near-duplicate patients (the same
-- person registered twice under a different source_system). We don't
-- silently delete them here -- staging should stay close to the raw data.
-- Deduplication logic belongs in the dimension layer, where the
-- business decision of "which record wins" is made explicitly.

select
    trim(patient_id)                       as patient_id,
    trim(source_system)                    as source_system,
    trim(district)                         as district,
    cast(age as int)                       as age,
    trim(gender)                           as gender,
    cast(registration_date as date)        as registration_date

from {{ source('raw', 'raw_patients') }}