select
    orders.customer_id,
    orders.order_id,
    items.order_item_id,
    orders.amount
from {{ ref('stg_orders') }} as orders
inner join {{ ref('raw_order_items') }} as items
    on orders.order_id = items.order_id
where orders.status = 'completed'

