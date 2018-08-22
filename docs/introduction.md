---
sidebarDepth: 0
---

# Introduction

## Welcome to the Prefect Preview!

Thank you for being one of our early partners. Your feedback is critical to making sure Prefect does everything it's supposed to do. You can always reach us at [help@prefect.io]().

We're very excited to share what we've been working on. This first preview release is `0.3.0`, which includes all the tools for building, testing, and executing workflows locally.

### Overview

Prefect is a new workflow management system designed for modern data infrastructures.

Users organize `Tasks` into `Flows`, and Prefect takes care of the rest! With a minimal but expressive API and intelligent defaults, it stays out of your way until you need it.

### What works now 🚀

Prefect `0.3.0` is a nearly-complete implementation of Prefect's core workflow logic. We're confident it can be used to design a wide variety of data workflows, and we're ready for you to kick the tires!

This release supports:

- designing custom `Tasks`
- composing tasks into `Flows` with either a functional or imperative API
- `FlowRunners` and `TaskRunners` for complete management of the workflow execution process, including all possible state transitions
- advanced execution patterns including automatic caching, triggers, pausing, dataflow, and retries
- basic visualization (static GraphViz charts and animated Bokeh applications)

### What's coming soon ⏰

Prefect `0.3.0` does not include a few important features that will be available in future preview releases. Some of those features include:

- our scheduler, server, database, UI, and GraphQL API
- a standard library of tasks
- building flows as containers for distribution
- remote execution clusters
- Airflow backward-compatibility

Stay tuned for more...

### What we'd love to hear 📢

- Do you have a data engineering or data science use case that can't be expressed with Prefect's design tools?
- Do you have a use case that **can** be expressed, but you think it could be easier?
- Are any of our naming conventions or design choices confusing or non-obvious?
- As we get closer to releasing the platform tools (including UI and API), what features are important to you? How do you want to interact with your data?

Please note that Prefect is alpha software under active development by Prefect Technologies, Inc. This early preview is being provided to a limited number of partners to assist with development. By viewing or using the code or documentation, you are agreeing to the [alpha software end user license agreement](/license.html).

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and ensures that work is done correctly.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Installation

:::tip Requirements
Please note Prefect requires Python 3.4 or higher.
:::

```
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e ".[viz]"
```
To install all development dependencies (for running unit tests): `pip install -e ".[dev]"`

## What's Next?

Jump in with the [quick start](getting_started.html) or [tutorials](tutorials/), browse the [API reference docs](api/)... or just `import prefect`.
