---
sidebarDepth: 0
---

# Introduction

## Welcome to the Prefect Preview!

Thank you for being one of our early partners. Your feedback is critical to making sure Prefect does everything it's supposed to do. You can always reach us at [help@prefect.io](mailto:help@prefect.io).

## Core + Cloud

Prefect `0.4.0` is the biggest Prefect release yet -- just check out the [changelog](changelog.html#version-0-4-0)! Prefect Core was already the best tool for designing, testing, and running data workflows - and thanks to your feedback, it's even better now.

The biggest new feature in Core is that it introduces support for **Prefect Cloud**. Cloud enables a variety of stateful interactions, including:

- Scheduling
- GraphQL API including arbitrary database queries
- Building flows as containers
- Runtime secrets
- Remote execution clusters
- Permissions and authorization
- Projects and organization

If you don't have access to the Cloud preview yet, please [get in touch](mailto:help@prefect.io).

Prefect is already starting to power Prefect HQ itself, and we can't wait to see what you build.

Happy engineering!

~ The Prefect Team

## Installation

:::tip Requirements
Please note Prefect requires Python 3.4 or higher.
:::

To install Prefect with visualization support:

```
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e ".[viz]"
```

To install all development dependencies (for running unit tests): `pip install -e ".[dev]"`

## What's Next?

Jump in with the [quick start](getting_started.html) or [tutorials](tutorials/), browse the [API reference docs](api/)... or just `import prefect`.
