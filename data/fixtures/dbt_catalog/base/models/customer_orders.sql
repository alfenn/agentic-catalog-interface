select
    customer_id,
    count(*) as completed_order_count,
    sum(amount) as completed_revenue,
    min(order_date) as first_completed_order_date,
    max(order_date) as latest_completed_order_date
from {{ ref('stg_orders') }}
where status = 'completed'
group by customer_id

