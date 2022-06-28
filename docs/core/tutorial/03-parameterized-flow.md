---
sidebarDepth: 0
---

# Adding Parameters

!!! tip Follow along in the Terminal

    ```
    cd examples/tutorial
    python 03_parameterized_etl_flow.py
    ```



In the [last tutorial](/core/tutorial/02-etl-flow.html) we refactored the Aircraft ETL script into a Prefect Flow. However, the `extract_live_data` Task has been hard coded to pull aircraft data only within a particular area, in this case a 200 KM radius surrounding Dulles International Airport:

```python{4-5}
@task
def extract_live_data():
    # Get the live aircraft vector data around Dulles airport
    dulles_airport_position = aclib.Position(lat=38.9519444444, long=-77.4480555556)
    area_surrounding_dulles = aclib.bounding_box(dulles_airport_position, radius_km=200)

    print("fetching live aircraft data...")
    raw_aircraft_data = aclib.fetch_live_aircraft_data(area=area_surrounding_dulles)

    return raw_aircraft_data

```

It would be ideal to allow fetching data from a wide variety of areas, not just around a single airport. One approach would be to allow `extract_live_data` to take `lat` and `long` parameters. However, we can go a step further: it turns out that we already have airport position information in our reference data that we can leverage!

Let's refactor our Python function to take a user-specified airport along with the reference data:

```python{2, 4-10}
@task
def extract_live_data(airport, radius, ref_data):
    # Get the live aircraft vector data around the given airport (or none)
    area = None
    if airport:
        airport_data = ref_data.airports[airport]
        airport_position = aclib.Position(
            lat=float(airport_data["latitude"]), long=float(airport_data["longitude"])
        )
        area = aclib.bounding_box(airport_position, radius)

    print("fetching live aircraft data...")
    raw_aircraft_data = aclib.fetch_live_aircraft_data(area=area)

    return raw_aircraft_data
```

_(In case you're curious, `area=None` will fetch live data for all known aircraft, regardless of the area it's in)_

How might we make use of these function parameters within a Prefect `Flow`? By using `prefect.Parameter`:

```python{1,6,7,10}
from prefect import Parameter

# ...task definitions...

with Flow("Aircraft-ETL") as flow:
    airport = Parameter("airport", default="IAD")
    radius = Parameter("radius", default=200)

    reference_data = extract_reference_data()
    live_data = extract_live_data(airport, radius, reference_data)

    transformed_live_data = transform(live_data, reference_data)

    load_reference_data(reference_data)
    load_live_data(transformed_live_data)
```

Just like `Tasks`, `Parameters` are not evaluated until `flow.run()` is called, using default values if provided, or overridden values passed into `run()`:

```python
# Run the Flow with default airport=IAD & radius=200
flow.run()

# ...default radius and a different airport!
flow.run(airport="DCA")
```

Lastly, take note that our execution graph has changed -- fetching live data now depends on obtaining the reference data:

![Graph ETL](/prefect-tutorial-etl-parameterized-dataflow.png)

!!! warning Up Next!

What happens when a task fails? And how can we customize actions taken when things go wrong?


