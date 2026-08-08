-- stg_billing.sql
--
-- Cleans the raw billing table.

select
    trim(billing_id)               as billing_id,
    trim(appointment_id)           as appointment_id,
    cast(amount as numeric)        as amount,
    trim(payment_status)           as payment_status,
    trim(insurance_provider)       as insurance_provider

from {{ source('raw', 'raw_billing') }}