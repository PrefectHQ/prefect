---
description: Learn tips for using Prefect when you have large amounts of data.
tags:
    - big data
    - flow configuration
    - parallel execution
    - distributed execution
    - caching
search:
  boost: 2
---

# Big data with Prefect

In this guide you'll learn tips for working with large amounts of data in Prefect.
We'll focus on speed and efficiency.

## Accessing data

You want to access data and save intermediate results of your workflows in a way that is fast and efficient.
In Prefect, results are the name given to the returned objects from a task that is part of a flow.
By default, each result is stored in memory in the execution environment.
This behavior makes running tasks fast for small data, but can be problematic for large data.
For each task run Prefect introspects the arguments. TK also return value.
This add overhead for large data.

Let's use this NYC taxi data as an example.
Note that we don't recommend running this example.

### Prerequisites

1. The Python packages prefect, parquet, pandas installed
1. CLI connected to Prefect Cloud or a self-hosted Prefect server instance
1. Ability to fetch data from the internet (unless switch to random data TK)

```python title="etl.py"
from prefect import task, flow
import pandas as pd


@task
def extract(url: str):
    """Extract data"""
    df_raw = pd.read_parquet(url)
    print(df_raw.info())
    return df_raw


@task
def transform(df: pd.DataFrame):
    """Basic transformation"""
    df_transformed["tip_fraction"] = df["tip_amount"] / df["total_amount"]
    print(df_transformed.info())
    return df_transformed


@task
def load(df: pd.DataFrame):
    """Save data"""
    df.to_parquet("s3://my-bucket/nyc_yellow_tax_data/2023/09.parquet")
    print("Data saved")


@flow(log_prints=True)
def etl(url: str):
    """ETL pipeline"""
    df_raw = extract(url)
    df = transform(quote(df_raw))  # quote to avoid introspection
    load(df)


if __name__ == "__main__":
    url = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-09.parquet"
    etl(url)

```

## Options for optimizing flows for large data

1. Remove task introspection
1. Write task results to cloud storage such as S3
1. Write out data using Prefect cloud library pre-built tasks
1. Use caching of task results
1. Use a distributed executor

### Remove task introspection

When a task is called from a flow, each argument is introspected by Prefect, by default.
You can disable this behavior for a task by wrapping the argument using [`quote`](https://docs.prefect.io/latest/api-ref/prefect/utilities/annotations/#prefect.utilities.annotations.quote) like this:

```python hl="9" title="etl_quote.py"
...
from prefect.utilities.annotations import quote
...

@flow(log_prints=True)
def etl(url: str):
    """ETL pipeline"""
    df_raw = extract(url)
    df = transform(quote(df_raw))  # quote to avoid introspection
    load(df)


```

### Cache task results

Caching is discussed in detail in the [tasks concept page of the docs](/concepts/tasks.md/#caching), so we won't discuss it in detail here. Just know that it requires result persistence and can save you time and compute by avoiding the need to re-run tasks.
