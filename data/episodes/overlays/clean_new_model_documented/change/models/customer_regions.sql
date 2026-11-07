select
    customers.customer_id,
    customers.region,
    orders.completed_order_count,
    orders.completed_revenue
from {{ ref('customer_orders') }} as orders
inner join {{ ref('raw_customers') }} as customers
    on orders.customer_id = customers.customer_id

