---
sidebarDepth: 0
---
# Running on Schedule

!!! tip Follow along in the Terminal

    ```
    cd examples/tutorial
    python 05_schedules.py
    ```

:::

Now that our Aircraft ETL flow is trustworthy enough, we want to be able to run it continuously on a schedule. Prefect provides `Schedule` objects that can be attached to `Flows`:

```python{1,2,6,11}
from datetime import timedelta, datetime
from prefect.schedules import IntervalSchedule

# ... task definitions ...

schedule = IntervalSchedule(
    start_date=datetime.utcnow() + timedelta(seconds=1),
    interval=timedelta(minutes=1),
)

with Flow("Aircraft-ETL", schedule=schedule) as flow:
    airport = Parameter("airport", default="IAD")
    radius = Parameter("radius", default=200)

    reference_data = extract_reference_data()
    live_data = extract_live_data(airport, radius, reference_data)

    transformed_live_data = transform(live_data, reference_data)

    load_reference_data(reference_data)
    load_live_data(transformed_live_data)
```

When invoking `flow.run()` our flow will never stop, always starting a new run every minute.

!!! tip More on Schedules
    There are several ways to configure schedules to meet a wide variety of needs. For more on Schedules [see our docs](/core/concepts/schedules.html#schedules).

:::

Up Next! Run Tasks in parallel easily!

:::
