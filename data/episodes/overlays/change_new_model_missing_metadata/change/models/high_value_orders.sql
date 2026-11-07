select *
from {{ ref('stg_orders') }}
where status = 'completed'
  and amount >= 100

