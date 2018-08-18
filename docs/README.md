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


## Hello, world!

```python
from prefect import task, Flow

@task
def say_hello():
    print("Hello, world!")

with Flow('My First Flow') as flow:
    say_hello()

flow.run() # "Hello, world!"
```
