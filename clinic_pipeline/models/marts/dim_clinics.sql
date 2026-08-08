-- dim_clinics.sql
select
    clinic_id,
    clinic_name,
    district,
    latitude,
    longitude
from {{ ref('stg_clinics') }}