---
home: true
heroImage: /Logo.svg
footer: Copyright © 2018-present Prefect Technologies, Inc.
---
<div class='hero'>
    <div style="display: flex;">
        <p class='action'>
            <router-link to="introduction.html" class="nav-link action-button">Read the docs</router-link>
        </p>
        <p class='action'>
            <router-link to="agreement.html" class="nav-link action-button">Get the code</router-link>
        </p>
    </div>
    <p style="font-size: 13px; font-style: italic;">
        Prefect is alpha software under active development by Prefect Technologies, Inc. This early preview is being provided to a limited number of partners to assist with development. By viewing or using the code or documentation, you are agreeing to the <a href='license.html'>alpha software end user license agreement</a>.
    </p>
</div>

<div class='features'>
    <div class='feature'>
        <h2>Automate all the things</h2>
        <p>If you can do it with Python, you can automate it with Prefect.</p>
    </div>
    <div class='feature'>
        <h2>Test local, deploy global</h2>
        <p>Workflows are developed and tested locally, then deployed for execution at scale.</p>
    </div>
    <div class='feature'>
        <h2>Simple but powerful</h2>
        <p>Prefect's beautiful API is powered by Dask and Kubernetes, so it's ready for anything.</p>
    </div>
</div>
<div class='features' style="padding-bottom: 0px; margin-top: 1em;"></div>

### Prefect

We've reimagined data engineering for the data science era. Prefect is a new workflow management system, designed for modern infrastructure. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](/introduction.html); get the [code](/agreement.html); ask us [anything](mailto:help@prefect.io)!


### Hello, world!

```python
from prefect import task, Flow

@task
def say_hello():
    print("Hello, world!")

with Flow('My First Flow') as flow:
    say_hello()

flow.run() # "Hello, world!"
```
