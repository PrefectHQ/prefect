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

To build documentation, run this from the root `prefect` directory (note that `prefect` must be `pip` installed in editable mode for this to succeed):
```bash
yarn docs:build
yarn docs:deploy
```

### Style Guide for Docstrings

`Prefect` auto-generates markdown files from the package's docstrings, which [VuePress](https://vuepress.vuejs.org/) compiles into static html. In order for docstrings to compile correctly, please follow the following rules:
- all documentation about class initialization should go into the class docstring, _not_ the `__init__` method docstring
- class method docstrings will be formatted into a table, which currently does not support language-specific syntax highlighthing.  Consequently, code blocks within such docstrings should not contain a language identifier (e.g. ` ```python `); however, code blocks within standalone functions should contain a language identifier.  To illustrate:
````python
def f(x: list):
    """
    Multiplies all elements of the list by 2.

    Args:
        - x (list): a list of numbers

    Example:
    ```python
    f([1, 2, 3]) # Returns [2, 4, 6]
    ```
   """ 
    return [2 * i for i in x]
````
vs.
````python
class Example:
    def f(self, x: list):
        """
        Multiplies all elements of the list by 2.

        Args:
            - x (list): a list of numbers

        Example:
        ```
        f([1, 2, 3]) # Returns [2, 4, 6]
        ```
       """ 
        return [2 * i for i in x]
````
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
