-- mart_sla_performance.sql
--
-- Business-ready summary: SLA compliance by clinic.
-- SLA target is defined here as: attended appointments with a wait time
-- of 30 minutes or less. This threshold is a reasonable, commonly-cited
-- outpatient benchmark -- adjust SLA_TARGET_MINUTES below if you want to
-- test a different target.

{% set sla_target_minutes = 30 %}

select
    cl.clinic_id,
    cl.clinic_name,
    cl.district,
    count(*)                                                        as attended_appointments,
    count(*) filter (where a.wait_time_minutes <= {{ sla_target_minutes }})
                                                                     as within_sla_count,
    round(
        100.0 * count(*) filter (where a.wait_time_minutes <= {{ sla_target_minutes }})
        / nullif(count(*), 0),
        1
    )                                                                as sla_compliance_pct,
    round(avg(a.wait_time_minutes), 1)                              as avg_wait_time_minutes

from {{ ref('fact_appointments') }} a
inner join {{ ref('dim_clinics') }} cl
    on a.clinic_id = cl.clinic_id

where a.status = 'attended'

group by 1, 2, 3
order by sla_compliance_pct asc