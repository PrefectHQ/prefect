---
home: true
heroImage: /assets/logomark-color.svg
heroTitle: Prefect (Preview)
tagline: Don't Panic.
footer: Copyright © 2018-present Prefect Technologies, Inc.
---

<div class="hero">
<div class="action">

<button class="action-button">
<router-link to="introduction.html">Read the docs</router-link>
</button>
<button class="action-button">
<router-link to="agreement.html">Get the code</router-link>
</button>

Prefect is alpha software under active development by Prefect Technologies, Inc. This early preview is being provided to a limited number of partners to assist with development. By accessing or using the code or documentation, you are agreeing to the [alpha software end user license agreement](/license.html)\.
{.disclaimer}

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

Read the [docs](/introduction.html); get the [code](/agreement.html); ask us [anything](mailto:help@prefect.io)!

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
