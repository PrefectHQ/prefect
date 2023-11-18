---
description: Learn tips for using Prefect when you have large amounts of data.
tags:
    - tasks
    - task runners
    - flow configuration
    - parallel execution
    - distributed execution
    - Dask
    - Ray
search:
  boost: 2
---

# Big data with Prefect

In this guide you'll learn tips for working with large amounts of data in Prefect.
We'll focus on speed and efficiency.

## Accessing data

You want to access data and save intermediate results in a way that is fast and efficient.
With Prefect, results (the return values) of each task are stored in memory in your execution environment by default.
This behavior makes running tasks fast for small data, but can be problematic for large data.
For each task run Prefect introspects the arguments. TK also return value.
This add overhead for large data.

Let's use this as an example:

```python
from prefect import task, flow
import pandas as pd

@task
def load_data():
    df_raw = pd.read_parquet("https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-09.parquet")
    print(df_raw.info())
    return df_raw

@task
def transform(df_raw: pd.DataFrame):
    df_transformed["tip_fraction"] = df["tip_amount"] / df["total_amount"]
    print(df_transformed.info())
    return df_transformed

@flow(log_prints=True)
def etl():
    df_raw = load_data()
    df = transform(df_raw)

if __name__ == "__main__":
    etl()
```
