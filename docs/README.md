<p align="center" >
   <img src="https://images.ctfassets.net/gm98wzqotmnx/3Ufcb7yYqcXBDlAhJ30gce/c237bb3254190795b30bf734f3cbc1d4/prefect-logo-full-gradient.svg" width="500" style="max-width: 500px;">
</p>

<p align="center">
    <a href=https://circleci.com/gh/PrefectHQ/prefect/tree/master>
        <img src="https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=shield&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344">
    </a>
    <a href="https://codecov.io/gh/PrefectHQ/prefect">
        <img src="https://codecov.io/gh/PrefectHQ/prefect/branch/master/graph/badge.svg" />
    </a>
    <a href=https://github.com/ambv/black>
        <img src="https://img.shields.io/badge/code%20style-black-000000.svg">
    </a>
    <a href="https://pypi.org/project/prefect/">
        <img src="https://img.shields.io/pypi/dm/prefect.svg?color=%2327B1FF&label=installs&logoColor=%234D606E">
    </a>
    <a href="https://hub.docker.com/r/prefecthq/prefect">
        <img src="https://img.shields.io/docker/pulls/prefecthq/prefect.svg?color=%2327B1FF&logoColor=%234D606E">
    </a>
    <a href="https://www.prefect.io/slack">
        <img src="https://img.shields.io/static/v1.svg?label=chat&message=on%20slack&color=27b1ff&style=flat">
    </a>
</p>

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

Read the [docs](/core/); get the [code](https://github.com/PrefectHQ/prefect); ask us [anything](https://www.prefect.io/slack)!

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
