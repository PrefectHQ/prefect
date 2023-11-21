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

## Options for optimizing your Python code with Prefect for big data

1. Remove task introspection - save time
1. Don't wrap the function in a task - save time - but quote is better b/c can observe and get other benefits such as retries (is there any reason this would be much faster than the one above? No API calls, so should be a bit faster.)
1. Write task results to cloud storage such as S3 using a block - save memory
1. Write out data using Prefect cloud library pre-built tasks - save memory
1. Use caching of task results - save time, compute
1. Use a distributed executor - save time, compute
1. Compress results -

### Remove task introspection

When a task is called from a flow, each argument is introspected by Prefect, by default.
To speed up your workflow runs can disable this behavior for a task by wrapping the argument using [`quote`](https://docs.prefect.io/latest/api-ref/prefect/utilities/annotations/#prefect.utilities.annotations.quote) like this:

```python hl="9" title="etl_quote.py"
...
from prefect.utilities.annotations import quote
...

@flow(log_prints=True)
def etl(url: str):
    """ETL pipeline"""
    df_raw = extract(url)
    df = transform(quote(df_raw))
    load(df)
```

Introspection can be a significant performance hit when the object is a large collection, such as a large dictionary or data frame, and each element needs to be visited. Using `quote` will disable task dependency tracking for the wrapped object, but likely will increase performance.

### Write task results to cloud storage

Save memory by writing results to disk.
You could use write results from a task to cloud provider storage such as AWS S3.
You could use a storage block from a Prefect cloud integration library such as prefect-aws to save your configuration information.
Learn more about blocks [here](/concepts/blocks/).

Install the library, register the block with the server, create your storage block, and then use the block in your flow.

```python hl="" title="etl_s3.py"
...
from prefect_aws.s3 import S3Bucket

my_s3_block = S3Bucket.load("MY_BLOCK_NAME")

...
@task(result_storage=my_s3_block)

```

Now the result of the task will be written to S3.

### Cache task results

Caching allows you to avoid re-running tasks when not needed. Caching is discussed in detail in the [tasks concept page of the docs](/concepts/tasks.md/#caching), so we won't discuss it in detail here. Caching requires result persistence and can save you time and compute.
