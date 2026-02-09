select customer_id, name, created_at::date as created_at
from {{ ref('customers') }}
