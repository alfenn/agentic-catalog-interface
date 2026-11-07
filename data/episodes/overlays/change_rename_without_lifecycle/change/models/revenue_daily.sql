select
    order_date,
    count(*) as completed_order_count,
    sum(amount) as completed_revenue
from {{ ref('stg_orders') }}
where status = 'completed'
group by order_date

