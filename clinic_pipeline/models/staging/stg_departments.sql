-- stg_departments.sql
--
-- Cleans the raw departments table.

select
    trim(department_id)    as department_id,
    trim(department_name)  as department_name

from {{ source('raw', 'raw_departments') }}