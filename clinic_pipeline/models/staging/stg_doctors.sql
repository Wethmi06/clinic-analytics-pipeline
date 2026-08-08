-- stg_doctors.sql
--
-- Cleans the raw doctors table.
-- years_experience is cast from text to an integer.

select
    trim(doctor_id)                  as doctor_id,
    trim(name)                       as doctor_name,
    trim(department_id)              as department_id,
    trim(clinic_id)                  as clinic_id,
    cast(years_experience as int)    as years_experience

from {{ source('raw', 'raw_doctors') }}