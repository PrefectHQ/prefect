select order_id, customer_id, amount, order_date::date as order_date
from {{ ref('orders') }}
