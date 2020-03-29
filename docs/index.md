---
home: true
heroImage: /assets/wordmark-color-vertical.svg
heroText: ' '
footer: Copyright © 2018-present Prefect Technologies, Inc.
---

<div class="hero">
    <div class="action">
        <button class="action-button">
            <router-link to="core/">
                Prefect Core
            </router-link>
        </button>
        <button class="action-button">
            <router-link to="orchestration/">
                Orchestration
            </router-link>
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

Prefect Cloud is powered by GraphQL, Dask, and Kubernetes, so it's ready for anything.

</div>
</div>

---

### Prefect

We've rebuilt data engineering for the data science era.

Prefect is a new workflow management system, designed for modern infrastructure and powered by the open-source Prefect Core workflow engine. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](/core/); get the [code](https://github.com/PrefectHQ/prefect); ask us [anything](https://join.slack.com/t/prefect-community/shared_invite/enQtODQ3MTA2MjI4OTgyLTliYjEyYzljNTc2OThlMDE4YmViYzk3NDU4Y2EzMWZiODM0NmU3NjM0NjIyNWY0MGIxOGQzODMxNDMxYWYyOTE)!

### Hello, world! 👋

```python
from prefect import task, Flow, Parameter


@task(log_stdout=True)
def say_hello(name):
    print("Hello, {}!".format(name))


with Flow("My First Flow") as flow:
    name = Parameter('name')
    say_hello(name)


flow.run(name='world') # "Hello, world!" 
flow.run(name='Marvin') # "Hello, Marvin!" 
```
