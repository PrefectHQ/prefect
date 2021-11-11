# Code Style

## Black formatting

Prefect's code is formatted using the [black](https://github.com/ambv/black) style. This style is checked in a CI step, and merges to master are prevented if code does not conform.

To apply black to your code, run black from the root Prefect directory:

```bash
cd prefect
black .
```

Formatting can be easy to forget when developing, so you may choose to install a pre-push hook for black, as follows:

```
pip install pre-commit # installs pre-commit package
cd prefect/ # make sure you are in the root directory of the prefect repo
pre-commit install --hook-type pre-push # creates necessary git hook files
```

There is already a pre-commit config file contained in the repo that creates the pre-push hook for black. Once installed, you won't be allowed to `git push` without passing black.

In addition, a number of extensions are available for popular editors that will automatically apply black to your code.

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

* The return value is indicated by the word `Returns:` followed by a Markdown list that indicates the return value's type and description. Note that a list is required even though there is only a single return type:

  ```
  Returns:
      - int: a number representing the output
  ```

* Any errors raised by a function are indicated by the word `Raises:` followed by a Markdown list that indicates each exception's type and description:

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

## Mypy typing

Prefect's code is statically-typed using [mypy](http://mypy-lang.org/). Type checking is validated as a CI step, and merges to master are prevented if code does not pass type checks.

While we would prefer for all of Prefect's code to be typed, that creates an undesirable friction for new contributors. Therefore, mypy is only _required_ for "important" code (generally, files in the `core/` and `engine/` directories), but encouraged elsewhere. Test files are never checked for typing. To run mypy locally:

```bash
cd prefect
mypy src
```

As a general rule, mypy typing requires all function arguments and return values to be annotated.
