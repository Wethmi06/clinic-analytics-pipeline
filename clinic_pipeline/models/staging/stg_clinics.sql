-- stg_clinics.sql
--
-- Cleans the raw clinics table (real OpenStreetMap data, loaded as all-text).
-- This is the simplest staging model in the project: rename/trim text
-- columns, cast latitude/longitude from text to actual numbers.

select
    trim(clinic_id)                as clinic_id,
    trim(name)                     as clinic_name,
    trim(district)                 as district,
    cast(latitude as numeric)      as latitude,
    cast(longitude as numeric)     as longitude

from {{ source('raw', 'raw_clinics') }}