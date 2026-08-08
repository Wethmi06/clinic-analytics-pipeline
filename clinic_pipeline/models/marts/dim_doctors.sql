-- dim_doctors.sql
--
-- Enriches each doctor with their department name and clinic name
-- directly, so downstream marts/dashboard queries don't need extra joins
-- for simple lookups.

select
    doc.doctor_id,
    doc.doctor_name,
    doc.years_experience,
    doc.department_id,
    dept.department_name,
    doc.clinic_id,
    cl.clinic_name,
    cl.district as clinic_district

from {{ ref('stg_doctors') }} doc
left join {{ ref('dim_departments') }} dept
    on doc.department_id = dept.department_id
left join {{ ref('dim_clinics') }} cl
    on doc.clinic_id = cl.clinic_id