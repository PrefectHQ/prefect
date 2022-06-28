---
sidebarDepth: 0
---

# Introduction to ETL

Before we even `import prefect`, let's begin by reviewing a typical real-life ETL workflow.

!!! tip Follow along in the Terminal

    Grab the tutorial code:

    ```
    git clone --depth 1 https://github.com/PrefectHQ/prefect.git
    cd prefect/examples/tutorial

    # Optionally, create a virtual environment for this tutorial
    python3 -m venv env  
    source env/bin/activate   

    pip install -r requirements.txt
    ```

    Run this example:

    ```
    python 01_etl.py
    ```



## "Aircraft ETL" Example

In this tutorial, we are trying to fetch and store information about live aircraft information to use in a future analysis. This future analysis requires pulling, cleaning, and merging data from multiple sources. In this case we are using "live" aircraft data (positional information) and "reference" data (airport locations, flights, route plan information).

Before we bring any Prefect concepts into the mix, let's start with a reference implementation that solves our problem:

```python
import aircraftlib as aclib

dulles_airport_position = aclib.Position(lat=38.9519444444, long=-77.4480555556)
area_surrounding_dulles = aclib.bounding_box(dulles_airport_position, radius_km=200)

# Extract: fetch data from multiple data sources
ref_data = aclib.fetch_reference_data()
raw_aircraft_data = aclib.fetch_live_aircraft_data(area=area_surrounding_dulles)

# Transform: clean the fetched data and add derivative data to aid in the analysis
live_aircraft_data = []
for raw_vector in raw_aircraft_data:
    vector = aclib.clean_vector(raw_vector)
    if vector:
        aclib.add_airline_info(vector, ref_data.airlines)
        live_aircraft_data.append(vector)

# Load: save the data for future analysis
db = aclib.Database()
db.add_live_aircraft_data(live_aircraft_data)
db.update_reference_data(ref_data)
```

The advantages of the above code is that it is simple to read. However, its simplicity is matched only by the number of disadvantages. First and foremost, the workflow is strictly linear:

![Linear ETL](/prefect-tutorial-etl-linear.png)

This leads to missed compute opportunities:

- Both "extract" steps could be parallelized to save time
- Similarly, both "load" steps can be parallelized to save time

Additionally, an unnecessarily-linear flow introduces a second problem: workflow failures now affect unnecessarily-related code:

- If fetching live aircraft data fails but we already fetched the updated reference data we will simply throw away the reference data.
- If there is an unexpected issue while cleaning the data, the reference data will be lost.
- If data transformation was successful but the DB is unavailable, then the data is lost and the workflow will need to start from the beginning.

These poor behaviors are indicators that the script is not well engineered. The "missing engineering" involved here are the things that we at Prefect refer to as "negative engineering", or the inherent precautions one must take to ensure that the workflow will be well-behaved. The code above has very little (if any) of these precautions.

Next, we'll take our ETL example and use Prefect to improve the behavior of our workflow.

