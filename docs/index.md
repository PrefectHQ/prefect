---
home: true
heroText: ' '
tagline: ' '
footer: Copyright © 2018-present Prefect Technologies, Inc.
---

<div class="hero">
   <img src="/assets/prefect-logo-gradient-navy.svg" width="500" style="max-width: 500px;">
   <p class="description">Don't Panic.</p>
    <div class="action">
        <router-link to="core/">
            <button class="action-button"  to="core/">
                Core Workflow Engine
            </button>
         </router-link>
        <router-link to="orchestration/">
            <button class="action-button">
                Orchestration & API
            </button>
        </router-link>
    </div>
</div>

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2.0</a> release? Prefect 2.0 and <a href="https://app.prefect.cloud">Prefect Cloud 2.0</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

Prefect 1.0 Core, Server, and Cloud are our first-generation workflow and orchestration tools. You can continue to use them and we'll continue to support them while migrating users to Prefect 2.0.

If you're ready to start migrating your workflows to Prefect 2.0, see our [migration guide](https://docs.prefect.io/migration-guide/).

If you are unsure which Prefect version to choose for your specific use case, [this Prefect Discourse page](https://discourse.prefect.io/t/should-i-start-with-prefect-2-0-orion-skipping-prefect-1-0/544) may help you decide.

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

Read the [docs](/core/); get the [code](https://github.com/PrefectHQ/prefect); ask us [anything](https://www.prefect.io/slack); chat with the community via [Prefect Discourse](https://discourse.prefect.io/)!

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
