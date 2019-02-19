---
sidebarDepth: 1
---

# Installing Prefect

## Requirements

Prefect requires Python 3.4+, and Python 3.6 or higher is recommended.

## Installation

To install Prefect, simply run:

```bash
pip install prefect
```

## Optional dependencies

Prefect ships with a number of optional dependencies, which can be installed like this:

```bash
pip install "prefect[extra1, extra2]"
```

The extra packages include:

- `all_extras`: includes all of the optional dependencies
- `dev`: tools for developing Prefect itself
- `templates`: tools for working with string templates
- `viz`: tools for visualizing Prefect flows
