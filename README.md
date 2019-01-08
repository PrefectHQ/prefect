[![CircleCI](https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=svg&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344)](https://circleci.com/gh/PrefectHQ/prefect/tree/master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

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

This will install optional visualization utilities:
```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install ".[viz]"
```

## Documentation

The full Prefect documentation including API references, tutorials, concept explinations, and more are available at https://docs.prefect.io

## Development

### Install `dev` package

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install -e ".[dev]"
```

### Run unit tests

```bash
cd prefect
pytest
```

### Black formatting

Merging to master in Prefect requires that your code passes [black](https://github.com/ambv/black). This can be easy to forget when developing, and for that reason some developers may choose to install a pre-push hook for black, as follows:
```
pip install pre-commit # installs pre-commit package
cd prefect/ # make sure you are in the root directory of the prefect repo
pre-commit install --hook-type pre-push # creates necessary git hook files
```
There is already a pre-commit config file contained in the repo that creates the pre-push hook for black.  Now, you won't be allowed to `git push` without passing black.


### Build documentation

To view documentation locally:

```bash
cd prefect
yarn install # only the first time!
yarn docs:dev
```

And then open [http://localhost:8080](http://localhost:8080) to see the freshly built documentation.

### Style guide for docstrings

`Prefect` auto-generates markdown files from the package's docstrings, which [VuePress](https://vuepress.vuejs.org/) compiles into static html. In order for docstrings to compile correctly, please follow the following rules:

- all documentation about class initialization should go into the class docstring, _not_ the `__init__` method docstring
- argument, return and raise lists should be formatted as markdown lists with colons denoting the beginning of a description `- name (type):` For example:

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
    the argument type.  Also, all other documentation can contain markdown.

    Returns:
        - None

    Raises:
        - ValueError: if `x == 0`
    """
```

- in order for your new functions / classes / modules to be compiled into documentation, you must do two things:
  1. update the `outline.toml` file within the `docs/` directory, specify the following information about your page (or update an existing page):
     - the location and filename of the markdown page will be inferred from your header specification
     - if your module has a module-level docstring, this will be displayed at the top of the page
     - `title`: a string specifying the displayed title of the page
     - `classes`: an optional list of strings specifying all documented classes on this page
     - `functions`: an optional list of strings specifying all documented standalone functions on this page
  2. update `docs/.vuepress/config.js` to include your new page / section / etc. in the sidebar

For example:
```
[pages.utilities.collections]
title = "Collections"
module = "prefect.utilities.collections"
classes = ["DotDict"]
functions = ["merge_dicts", "as_nested_dict", "dict_to_flatdict", "flatdict_to_dict"]
```
