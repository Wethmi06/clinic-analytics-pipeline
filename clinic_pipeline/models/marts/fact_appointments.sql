-- fact_appointments.sql
--
-- One row per appointment (the core fact table). Every appointment is
-- joined through int_patient_dedup_bridge so patient_id here always
-- refers to the canonical (deduplicated) patient -- never one of the
-- accidental duplicate raw_patient_id values.

select
    a.appointment_id,
    b.canonical_patient_id   as patient_id,
    a.doctor_id,
    a.clinic_id,
    a.department_id,
    a.icd10_code,
    a.booking_date,
    a.scheduled_date,
    a.lead_time_days,
    a.status,
    a.wait_time_minutes,
    (a.status = 'no_show')   as is_no_show,
    (a.status = 'attended')  as is_attended

from {{ ref('stg_appointments') }} a
left join {{ ref('int_patient_dedup_bridge') }} b
    on a.patient_id = b.raw_patient_id