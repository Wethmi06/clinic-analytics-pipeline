-- stg_diagnosis_codes.sql
--
-- Cleans the raw diagnosis codes table (real ICD-10-CM data from Day 2).

select
    trim(icd10_code)   as icd10_code,
    trim(description)  as description

from {{ source('raw', 'raw_diagnosis_codes') }}