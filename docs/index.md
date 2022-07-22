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


Prefect Core is now Prefect 1.0! Check [this blog post](https://www.prefect.io/blog/prefect-core-is-now-prefect-1-0/) to learn more.

When we say Prefect 1.0, we mean it as a generation of a product, not as a specific release. This distinction is important since we are actively working on a new generation of Prefect based on [the Orion engine](https://www.prefect.io/blog/announcing-prefect-orion) &mdash; [Prefect 2.0](https://www.prefect.io/blog/introducing-prefect-2-0/)! The documentation for Prefect 2.0 is available on [orion-docs.prefect.io](https://orion-docs.prefect.io). 

If you use a previous version of Prefect (before the 1.0 release), you may either:

- Transition your flows to the latest 1.0 release &mdash; for more details, check out our [Upgrading to Prefect 1.0](/orchestration/faq/upgrading_1.0) guide and [Changelog](/api/latest/changelog/).
- Start using Prefect 2.0 already! You can even sign up for a free [Cloud 2.0](https://orion-docs.prefect.io/ui/cloud/) account on [beta.prefect.io](https://beta.prefect.io/).


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
