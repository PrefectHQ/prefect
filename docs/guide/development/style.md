# Code Style

## Black formatting

Prefect's code is formatted using the [black](https://github.com/ambv/black) style. Merges to master are prevented if code does not conform, and this is checked both as a unit test and a separate CI step, for clarity.

To apply black to your code, simply run black from the root Prefect directory:

```bash
cd prefect
black .
```

Please note that black requires Python 3.6+ (though Prefect does not).

Formatting can be easy to forget when developing, so you may choose to install a pre-push hook for black, as follows:

```
pip install pre-commit # installs pre-commit package
cd prefect/ # make sure you are in the root directory of the prefect repo
pre-commit install --hook-type pre-push # creates necessary git hook files
```

There is already a pre-commit config file contained in the repo that creates the pre-push hook for black. Once installed, you won't be allowed to `git push` without passing black.

In addition, a number of extensions are available for popular editors that will automatically apply black to your code.

## Mypy typing

Prefect's code is statically-typed using [mypy](http://mypy-lang.org/). Merges to master are prevented if code does not pass type checks, and this test is performed both as a unit test and a separate CI step, for clarity.

While we would prefer for all of Prefect's code to be typed, that creates an undeseriable friction for new contributors. Therefore, mypy is only *required* for "important" code (generally, files in the `core/` and `engine/` directories), but encouraged elsewhere. Test files are never checked for typing. To run mypy only against required files, invoke it as a unit test:

```bash
cd prefect
pytest -k "mypy"
```

As a general rule, mypy typing requires all function arguments and return values to be annotated.

Prefect is compatible with Python 3.5+, so users should *not* use attribute annotations to indicate types, as those were introduced in Python 3.6. Inline comments should be used instead (`x = []  # type: List[int]`, for example).
