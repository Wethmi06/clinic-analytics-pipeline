-- fact_billing.sql
--
-- One row per billing record, linked to its appointment. patient_id is
-- pulled through fact_appointments so it's already deduplicated/canonical.

select
    bill.billing_id,
    bill.appointment_id,
    appt.patient_id,
    bill.amount,
    bill.payment_status,
    bill.insurance_provider

from {{ ref('stg_billing') }} bill
left join {{ ref('fact_appointments') }} appt
    on bill.appointment_id = appt.appointment_id