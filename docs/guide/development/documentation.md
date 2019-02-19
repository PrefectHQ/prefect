# Documentation

Documentation is incredibly important to Prefect, both for explaining its concepts to general audiences and describing its API to developers.

## Docstrings

Prefect auto-generates API documentation from docstrings by compiling them to Markdown. In order for docstrings to compile correctly, please follow these rules:

:::tip Docstring Formatting
- All documentation about class initialization should go into the class docstring, _not_ the `__init__` method docstring.
- Any references to "code" or variable names should be surrounded by backticks so it will be properly formatted in Markdown.
- Arguments are indicated by the word `Args:` followed by a Markdown list that indicates each argument's name, type, and description:
    ```
    Args:
        - x (int): a number that provides the initial value.
    ```


- The return value is indicated by the word `Returns:` followed by a Markdown list that indicates the return value's type and description. Note that a list is required even though there is only a single return type:

    ```
    Returns:
        - int: a number representing the output
    ```

- Any errors raised by a function are indicated by the word `Raises:` followed by a Markdown list  that indicates each exception's type and description:

    ```
    Raises:
        - ValueError: if the input is zero or negative
    ```

:::
Here is an example of a fully-documented module:

```python
"""
This docstring describes this module.
"""

def function(x: List[str] = None) -> int:
    """
    This is a function docstring.

    Args:
        - x (List[str], optional): any information about x

    Returns:
        - int: any details about the return value
    """
    pass


class Class:
    """
    This is the class docstring, which also describes its `__init__()` constructor.

    Note that __init__ does not require an annotation for `self` or for the return value
    (which is always `None`), as long as at least one other argument is typed.

    Args:
    - x (int): a number

    """

    def __init__(self, x: int):
        pass

    def method(self, x: int, y: float, z: str = None) -> int:
        """
        Something interesting about what this method does.

        Args:
            - x (int): any information about `x`
            - y (float): additional info about `y`
            - z (str, optional): defaults to `None`; note that codeblocks are not currently
                supported within arg docs

        Additional information if desired; note that backticks for code formatting
        is encouraged within argument descriptions, but should *not* be used in
        the argument type.  Also, all other documentation can contain Markdown.

        Returns:
            - int: details about the return value

        Raises:
            - ValueError: if `x == 0`
        """
        pass
```

## API Reference

Modules, functions, and classes must be explicitly added to the auto-generated documentation. First, update the `docs/outline.toml` file with the following information: - a header that describes the path to the generated Markdown file - a `title` for the generated Markdown file - `module`: an optional path to an importable module, whose docstring will be displayed at the top of the page - `classes`: an optional list of strings specifying all documented classes in the module - `functions`: an optional list of strings specifying all documented standalone functions in the module

For example, if the stylized module described above was importable at `prefect.utilities.example`, then we might add this to `outline.toml`:

```
[pages.utilities.example]
title = "Example Module"
module = "prefect.utilities.example"
classes = ["Class"]
functions = ["function]
```

If your module wasn't already in the reference docs, update `docs/.vuepress/config.js` to add it to the navigation sidebar. For example, the collections module from this example would be added to the "utilities" section:

```javascript
{
    title: 'prefect.utilities',
    collapsable: true,
    children: [
        'utilities/collections',
        'utilities/example',  // our new file
        ...
    ]
}
```

## Concepts

Prefect also includes a great deal of "concept" documentation, which covers features, tutorials, guides, and examples. This page is part of the concept documentation for development!

To write concept docs, simply add Markdown files to the `docs/docs` directory (or one of its subdirectories). To ensure that your page is displayed in the navigation, edit `docs/.vuepress/config.js` to include a reference to it.

## Previewing docs

Documentation (including both concepts and API references) is built and deployed with every merge to Prefect's master branch. Prior to merge, a GitHub check will allow you to see a hosted version of the documentation associated with every PR.

To preview docs locally, you'll first need to install Vuepress and its dependencies. This requires the [yarn](https://yarnpkg.com/) package manager. You only need to do this once:

```bash
cd prefect
yarn install
```

To launch a documentation preview:

```bash
cd prefect
yarn docs:dev
```

You'll see a status update as the docs build, and then an announcement that they are available on `http://localhost:8080`.

::: tip Hot-reloading docs
Concept docs will hot-reload every time you save a file, but API reference docs must be regenerated by restarting the server.
:::
