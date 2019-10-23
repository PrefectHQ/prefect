---
home: true
heroImage: /assets/wordmark-color-vertical.svg
heroText: " "
footer: Copyright © 2018-present Prefect Technologies, Inc.
---

<div class="hero">
    <div class="action">
        <button class="action-button">
            <router-link to="core/">
                Read the docs
            </router-link>
        </button>
        <a href="https://github.com/PrefectHQ/prefect">
            <button class="action-button">
                Get the code
            </button>
        </a>
        <a href="https://prefect.io/support" target="_blank" >
            <button class="action-button">
                Ask for help
            </button>
        </a>
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

Read the [docs](/core/); get the [code](https://github.com/PrefectHQ/prefect); ask us [anything](https://join.slack.com/t/prefect-public/shared_invite/enQtNzE5OTU3OTQwNzc1LTQ5M2FkZmQzZjI0ODg1ZTBmOTc0ZjVjYWFjMWExZDAyYzBmYjVmMTE1NTQ1Y2IxZTllOTc4MmI3NzYxMDlhYWU)!

### Hello, world! 👋

```python
from prefect import task, Flow

@task
def say_hello():
    print("Hello, world!")

with Flow("My First Flow") as flow:
    say_hello()

flow.run() # "Hello, world!"
```
