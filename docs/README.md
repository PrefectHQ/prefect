---
home: true
heroImage: /Logo.svg
actionText: Get Started →
actionLink: /introduction
features:
- title: Automate all the things
  details: If you can do it with Python, you can automate it with Prefect.
- title: Test local, deploy global
  details: Workflows are developed and tested locally, then deployed for execution at scale.
- title: Simple but powerful
  details: Prefect's beautiful API is powered by Dask and Kubernetes, so it's ready for anything.
footer: Copyright © 2018-present Prefect Technologies, Inc.
---

## What is Prefect?
Prefect is a workflow management system designed for modern data infrastructures.

## Examples

### Hello, Prefect!

```python
from prefect import task, Flow

@task
def say_hello():
    print("Hello, world!")

with Flow('Hello, world!') as flow:
    say_hello()

flow.run() # "Hello, world!"
```

### Hello, ETL!

```python
@task
def extract():
    """Get a list of data"""
    return [1, 2, 3]

@task
def transform(data):
    """Multiply the input by 10"""
    return [i * 10 for i in data]

@task
def load(data):
    """Print the data to indicate it was received"""
    print("Here's your data: {}".format(data))

with Flow('ETL') as flow:
    e = extract()
    t = transform(e)
    l = load(t)

flow.run() # prints "Here's your data: [10, 20, 30]"
```
