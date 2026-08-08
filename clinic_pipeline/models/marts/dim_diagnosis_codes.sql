-- dim_diagnosis_codes.sql
select
    icd10_code,
    description
from {{ ref('stg_diagnosis_codes') }}