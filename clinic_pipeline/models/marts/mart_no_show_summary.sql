-- mart_no_show_summary.sql
--
-- Business-ready summary: no-show rate by department and month.
-- This is the table the dashboard's main KPI view will query directly --
-- no joins needed downstream.

select
    date_trunc('month', a.scheduled_date)  as appointment_month,
    d.department_name,
    count(*)                                              as total_appointments,
    count(*) filter (where a.status = 'attended')         as attended_count,
    count(*) filter (where a.status = 'no_show')          as no_show_count,
    count(*) filter (where a.status = 'cancelled')         as cancelled_count,
    round(
        100.0 * count(*) filter (where a.status = 'no_show')
        / nullif(count(*) filter (where a.status in ('attended', 'no_show')), 0),
        1
    )                                                      as no_show_rate_pct,
    round(avg(a.lead_time_days), 1)                        as avg_lead_time_days

from {{ ref('fact_appointments') }} a
left join {{ ref('dim_departments') }} d
    on a.department_id = d.department_id

where a.scheduled_date <= current_date  -- exclude future/not-yet-happened appointments

group by 1, 2
order by 1, 2