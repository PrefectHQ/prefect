# Running on a Schedule

::: tip Follow along in the Terminal

```
cd examples/tutorial
python 05_schedules.py
```

:::

Now that our Aircraft ETL flow is trustworthy enough, we want to be able to run it continuously on a schedule. Prefect allows you to attach schedules directly to flows:

```python{1,2,6,8}
from datetime import timedelta
from prefect.schedules import IntervalSchedule

# ... task definitions ...

schedule = IntervalSchedule(interval=timedelta(minutes=1))

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

::: tip More on Schedules

There are several ways to configure schedules to meet a wide variety of needs. For more on Schedules [see our docs](https://docs.prefect.io/core/concepts/schedules.html#schedules).

:::

::: warning Up Next!

Run Tasks in parallel easily!

:::
