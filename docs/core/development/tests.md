# Testing

Prefect loves tests! There are a few important reasons to write tests:

- **Make sure your code works**

  Tests ensure that your code does the thing you intend it to do.

  If you have a function that adds two numbers, you'll want to test that it does, in fact, return their sum. If behavior depends on a configuration setting, ensure that changing that setting changes the behavior. In short, if you wrote a line of code, you should test that line works as expected.

- **Make sure your code doesn't not work**

  It may seem silly, but another important reason to write tests is to ensure that your code behaves as expected _even when it's broken_.

  This is especially important for a project like Prefect, which is focused on helping engineers when something unexpected happens to their code. For example, you could write tests about what you expect to happen if your function is called with incorrect (or no) arguments, or to ensure that any errors are properly trapped and handled.

* **Tests are documentation**

  Ultimately, your tests are the best documentation for your code.

  Another developer should be able to look at your tests and understand what your code does, how to invoke it, and what edge cases it contains. Therefore, try to write short, self-explanatory tests with descriptive titles.

* **Help future developers**

  As Prefect grows, your code will be reused in more and more places, by developers who may not be familiar with the details of your implementation. Therefore, your tests are an opportunity to ensure that your code is used correctly in the future.

  For example, if your code needs to be used in a certain way, or expects a certain configuration, or is always expected to return a certain output, or has any other details that might impact its ability to be used in the framework, write a test for it! At minimum, you'll help a future developer understand that you consciously chose to design your code a certain way.

## Writing tests

Prefect's tests are stored in the top-level `tests` directory. In general, the test directory layout mimics the library layout: a test at `tests/utilities/test_collections.py` is expected to test `prefect/utilities/collections.py`.

Prefect's tests are organized as submodules, meaning each directory has an `__init__.py` file. This means that module names can be safely reused for tests. If you create a new directory, be sure to put an (empty) `__init__.py` in it to ensure it gets picked up during test discovery.

Tests should have descriptive names that make it clear what you're testing. If necessary, add a docstring or comment to explain why you're testing this specific thing. If your test addresses a specific GitHub issue, please add a link to it in the docstring.

```python
# great test name! (from tests/core/test_task.py)
def test_class_instantiation_raises_helpful_warning_for_unsupported_callables():
    ...

# bad test name
def test_task_warning():
    ...
```

Prefect has a few [`pytest` fixtures](https://docs.pytest.org/en/stable/fixture.html) available for testing all available executors; see `conftest.py` for details.

## Running tests

Prefect uses `pytest` for unit testing. To run tests, invoke `pytest` from the root Prefect directory:

```bash
cd prefect
pytest
```

#### Running specific tests

To run a subset of tests, provide a filename or directory; to match a specific test name, use the `-k` flag:

```bash
# run all tests in the tests/core directory that contain the word "edge" in their title
pytest tests/core -k edge
```

#### Debugging

For debugging, we recommend installing the [`pdbpp`](https://github.com/pdbpp/pdbpp) package and running `pytest` with the `--pdb` flag (which will open the debugger on any error) or setting `breakpoint()` appropriately.

#### Stepwise execution

The `--sw` flag will exit `pytest` the first time it encounters an error; subsequent runs with the same flag will skip any tests that succeeded and run the failed test first.

## CI

CI will run automatically against any PR you open. Please run your tests locally first to avoid "debugging in CI", as this takes up resources that could be used by other contributors.

In CI, Prefect's unit tests are run against Python 3.7, 3.8, and 3.9. A separate "formatting" CI job is also run. Since formatting errors are common in PRs, we have found this to be a useful early-warning during development.

## Documentation

Prefect's API reference documentation is unit tested! If you don't describe an argument of any function, or use improperly formatted docstrings, you will get an error. For more details on docstrings, see the [documentation guide](documentation.md).
