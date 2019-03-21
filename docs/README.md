---
home: true
heroImage: /assets/logomark-color.svg
heroTitle: Prefect
tagline: Don't Panic.
footer: Copyright © 2018-present Prefect Technologies, Inc.
---

<div class="hero">
<div class="action">

<button class="action-button">
<router-link to="guide/">Read the docs</router-link>
</button>
<button class="action-button">
<router-link to="https://github.com/PrefectHQ/prefect">Get the code</router-link>
</button>

</div>
</div>
<div class="features">
<div class="feature">

## Automate all the things

If you can do it with Python, you can automate it with Prefect.

</div>
<div class="feature">

## Test local, deploy global

Workflows are developed and tested locally, then deployed for execution at scale.

</div>
<div class="feature">

## Simple but powerful

Prefect's beautiful API is powered by Dask and Kubernetes, so it's ready for anything.

</div>
</div>

---

### Prefect

We've rebuilt data engineering for the data science era.

Prefect is a new workflow management system, designed for modern infrastructure and powered by the open-source Prefect Core workflow engine. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](/guide/); get the [code](https://github.com/PrefectHQ/prefect); ask us [anything](mailto:help@prefect.io)!

### Hello, world! 👋

```python
from prefect import task, Flow

@task
def say_hello():
    print("Hello, world!")

with Flow('My First Flow') as flow:
    say_hello()

flow.run() # "Hello, world!"
```
