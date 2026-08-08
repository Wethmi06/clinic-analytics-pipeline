-- stg_appointments.sql
--
-- Cleans the raw appointments table.
-- This is the core fact table. Two messiness fields need careful handling:
--   - wait_time_minutes is blank for any appointment that isn't "attended"
--     (no-show, cancelled, scheduled) -- nullif converts that blank text
--     to a real NULL instead of failing the cast.
--   - icd10_code is intentionally missing (~3%) on some rows -- left as
--     NULL here on purpose, not filled in, so later layers (and dbt
--     tests) can surface and measure this data quality issue rather than
--     silently hiding it.
--
-- Deduplication: the raw table contains ~1% exact-duplicate rows
-- (simulating a pipeline glitch that re-inserted the same appointment
-- twice -- see generate_synthetic_data.py). We deduplicate here by
-- keeping only the first occurrence of each appointment_id, using
-- row_number() partitioned on appointment_id. This is the correct layer
-- to handle this: staging should produce one clean row per event.

with raw_cleaned as (

    select
        trim(appointment_id)                             as appointment_id,
        trim(patient_id)                                 as patient_id,
        trim(doctor_id)                                  as doctor_id,
        trim(clinic_id)                                  as clinic_id,
        trim(department_id)                              as department_id,
        nullif(trim(icd10_code), '')                     as icd10_code,
        cast(booking_date as date)                       as booking_date,
        cast(scheduled_date as date)                     as scheduled_date,
        cast(lead_time_days as int)                      as lead_time_days,
        trim(status)                                     as status,
        cast(nullif(trim(wait_time_minutes), '') as int) as wait_time_minutes,
        row_number() over (
            partition by trim(appointment_id)
            order by trim(appointment_id)
        ) as row_num

    from {{ source('raw', 'raw_appointments') }}

)

select
    appointment_id,
    patient_id,
    doctor_id,
    clinic_id,
    department_id,
    icd10_code,
    booking_date,
    scheduled_date,
    lead_time_days,
    status,
    wait_time_minutes

from raw_cleaned
where row_num = 1