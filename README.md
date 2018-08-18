[![CircleCI](https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=svg&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344)](https://circleci.com/gh/PrefectHQ/prefect/tree/master)

# Prefect

## Welcome to Prefect!

We've reimagined data engineering for the data science era. Prefect is a new workflow management system, designed for modern infrastructure. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

## License

Prefect is alpha software under active development by Prefect Technologies, Inc. This early preview is being provided to a limited number of partners to assist with development. By viewing or using the code or documentation, you are agreeing to the [alpha software end user license agreement](https://www.prefect.io/licenses/alpha-eula).

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and ensures that the rules are followed.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Installation

### Requirements

Prefect requires Python 3.4+.

### Install

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install .
```

## Development

### Install `dev` package

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e .[dev]
```

### Run unit tests

```bash
cd prefect
pytest
```

### Build documentation

To view documentation locally (run this from the root `prefect` directory):

```bash
yarn docs:dev
```

Open [http://localhost:8080](http://localhost:8080) to see the documentation.

### Style guide for docstrings

`Prefect` auto-generates markdown files from the package's docstrings, which [VuePress](https://vuepress.vuejs.org/) compiles into static html. In order for docstrings to compile correctly, please follow the following rules:

- all documentation about class initialization should go into the class docstring, _not_ the `__init__` method docstring
- argument and return lists should be formatted as markdown lists with colons denoting the beginning of a description `- name (type):` For example:

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
     - "top-level-doc": a module object which contains the docstring which will be displayed at the top of the generated page
  2. update `docs/.vuepress/config.js` to include your new page / section / etc. in the sidebar
