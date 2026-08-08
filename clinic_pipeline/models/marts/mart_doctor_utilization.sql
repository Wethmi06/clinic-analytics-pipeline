-- mart_doctor_utilization.sql
--
-- Business-ready summary: per-doctor workload and performance.

select
    doc.doctor_id,
    doc.doctor_name,
    doc.department_name,
    doc.clinic_name,
    doc.years_experience,
    count(a.appointment_id)                                   as total_appointments,
    count(*) filter (where a.status = 'attended')              as attended_count,
    count(*) filter (where a.status = 'no_show')               as no_show_count,
    round(
        100.0 * count(*) filter (where a.status = 'no_show')
        / nullif(count(*) filter (where a.status in ('attended', 'no_show')), 0),
        1
    )                                                           as no_show_rate_pct,
    round(avg(a.wait_time_minutes) filter (where a.status = 'attended'), 1)
                                                                 as avg_wait_time_minutes

from {{ ref('dim_doctors') }} doc
left join {{ ref('fact_appointments') }} a
    on doc.doctor_id = a.doctor_id
    and a.scheduled_date <= current_date

group by 1, 2, 3, 4, 5
order by total_appointments desc