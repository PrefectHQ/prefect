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

Prefect reimagines data engineering for the data science era. It's a new workflow management system, designed for modern infrastructure: users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](/introduction.html); get the [code](https://github.com/prefecthq/prefect); ask us [anything](mailto:help@prefect.io)!

## License

Prefect is alpha software under active development by Prefect Technologies, Inc. This early preview is being provided to a limited number of partners to assist with development. By viewing or using the code or documentation, you are agreeing to the [alpha software end user license agreement](/license.html).

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
