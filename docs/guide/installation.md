---
sidebarDepth: 1
title: Installation
---

# Installing Prefect

## Requirements

Prefect requires Python 3.5+, and Python 3.6 or higher is recommended.

## Installation

To install Prefect, simply run:

```bash
pip install prefect
```

## Optional dependencies

Prefect ships with a number of optional dependencies, which can be installed using "extras" syntax:

```bash
pip install "prefect[extra_1, extra_2]"
```

The extra packages include:

- `all_extras`: includes all of the optional dependencies
- `dev`: tools for developing Prefect itself
- `templates`: tools for working with string templates
- `viz`: tools for visualizing Prefect flows

## Development

For developing Prefect, see the [development guide](development/overview.md).
