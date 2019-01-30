---
home: true
heroImage: /assets/logomark-color.svg
footer: Copyright © 2018-present Prefect Technologies, Inc.
---
<div class='hero'>
    <div class='action'>
        <button class="action-button">
            <router-link to="introduction.html">Read the docs</router-link>
        </button>
        <button class="action-button">
            <router-link to="agreement.html">Get the code</router-link>
        </button>
    </div>
    <p class='note'>
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

### Prefect

We've reimagined data engineering for the data science era. Prefect is a new workflow management system, designed for modern infrastructure. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

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
