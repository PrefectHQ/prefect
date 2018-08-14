[![CircleCI](https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=svg&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344)](https://circleci.com/gh/PrefectHQ/prefect/tree/master)

# Prefect

## Welcome to Prefect!

Prefect is a workflow management system designed for modern data infrastructures.

Users organize `Tasks` into `Flows`, and Prefect takes care of the rest!


### "...Prefect?"

From the Latin *praefectus*, meaning "one who is in charge", a prefect is an official who oversees a domain and ensures that the rules are followed.

It also happens to be the name of a roving researcher for that wholly remarkable book, *The Hitchhiker's Guide to the Galaxy*.


## Installation

### Requirements

Prefect requires Python 3.4+.

### Install
```
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install .
```


## Development

### Install

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e .[dev]
```

### Unit Tests

```bash
cd prefect
pytest
```

## Documentation

To view documentation locally (run this from the root `prefect` directory):
```bash
yarn docs:dev
```
Open http://localhost:8080 to see the documentation.

### Style Guide for Docstrings

`Prefect` auto-generates markdown files from the package's docstrings, which [VuePress](https://vuepress.vuejs.org/) compiles into static html. In order for docstrings to compile correctly, please follow the following rules:
- all documentation about class initialization should go into the class docstring, _not_ the `__init__` method docstring
- argument lists should be formatted as markdown lists with colons denoting the beginning of a description `- name (type):` For example:
```python
def function(x: int, y: float, z: str = None):
    """
    Something interesting about what this function does.

    Args:
        - x (int): any information about `x`
        - y (float): additional info about `y`
        - z (str, optional): defaults to `None`

    Additional information if desired; note that backticks for code formatting
    is encouraged within argument descriptions, but should *not* be used in
    the list itself.  Also, all other documentation can contain markdown.

    Returns:
        - None
    """
```
- in order for your new functions / classes / modules to be compiled into documentation, you must do two things:
    1. in the `OUTLINE` list contained within `docs/generate_docs.py`, specify the following information about your page (or update an existing page):
        - `"page"`: the location and filename of the markdown page
        - `"title"`: the displayed title of the page
        - `"classes"`: a list of all documented classes on this page
        - `"functions"`: a list of all documented standalone functions on this page
    2. update `docs/.vuepress/config.js` to include your new page / section / etc. in the sidebar
