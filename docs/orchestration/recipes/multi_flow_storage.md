
# Multi Flow Storage

This recipe is for storing multiple flows inside a single [Docker storage object](/api/latest/storage.html#docker). This is useful when you have a suite of flows that registers off of a CI/CD process or if you want to reduce the number of images stored in a container registry. For this recipe we are going to put two example flows — [ETL](/core/advanced_tutorials/etl.html) and [Map Reduce](/core/concepts/mapping.html#reduce) — inside of the same Docker storage object.

[[toc]]

### Flow(s) Source

```python
from prefect import task, Flow

# ETL Flow

@task
def extract():
    return [1, 2, 3]


@task
def transform(data):
    return [i * 10 for i in data]


@task
def load(data):
    print("Here's your data: {}".format(data))


with Flow("ETL") as etl_flow:
    e = extract()
    t = transform(e)
    l = load(t)

# Map Reduce Flow

@task
def numbers_task():
    return [1, 2, 3]


@task
def map_task(x):
    return x + 1


@task
def reduce_task(x):
    return sum(x)


with Flow("Map / Reduce 🤓") as mr_flow:
    numbers = numbers_task()
    first_map = map_task.map(numbers)
    second_map = map_task.map(first_map)
    reduction = reduce_task(second_map)
```

### Adding Flows to Storage

In this code block we manually add our two flows to the same Docker storage object. Then the storage is built once and that new Docker storage object is assigned to both flows. When the flows are registered with the Prefect API, build is set to false (`build=False`) so the storage object is not built again.

```python
from prefect.storage import Docker

# Create our Docker storage
storage = Docker(registry_url="gcr.io/dev/", image_name="multi_flows", image_tag="0.1.0")

# Add both Flows to storage
storage.add_flow(etl_flow)
storage.add_flow(mr_flow)

# Build the storage
storage = storage.build()

# Reassign the new storage object to each Flow
etl_flow.storage = storage
mr_flow.storage = storage

# Register each flow without building a second time
etl_flow.register(project_name="...", build=False)
mr_flow.register(project_name="...", build=False)
```
