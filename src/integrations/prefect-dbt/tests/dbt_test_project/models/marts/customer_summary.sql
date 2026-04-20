select
    customer_id,
    customer_name,
    count(*) as order_count,
    sum({{ format_amount('amount') }}) as total_amount
from {{ ref('int_orders_enriched') }}
group by customer_id, customer_name
