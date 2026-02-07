select
    o.order_id,
    o.customer_id,
    c.name as customer_name,
    o.amount,
    o.order_date
from {{ ref('stg_orders') }} o
left join {{ ref('stg_customers') }} c on o.customer_id = c.customer_id
