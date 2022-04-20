---
description: Learn about writing tests for Prefect flows and tasks.
tags:
    - tutorial
    - testing
    - unit test
    - tasks
    - flows
    - development
---

# Testing Flows

Now that you have all of these awesome flows, you probably want to test them!

## Writing unit tests

Prefect provides a simple context manager for unit tests that allows you to run flows and tasks against a temporary local SQLite database.

```python
from prefect import flow
from prefect.utilities.testing import prefect_test_harness

@flow
def my_favorite_function():
    print("This function doesn't do much")
    return 42

def test_my_favorite_function():
  with prefect_test_harness():
      # run the flow against a temporary testing database
      assert my_favorite_function().result() == 42
```

For more extensive testing, you can leverage `prefect_test_harness` as a fixture in your unit testing framework. For example, when using `pytest`:

```python
import pytest
from prefect.utilities.testing import prefect_test_harness

from my_flows import my_favorite_function

@pytest.fixture(autouse=True)
def prefect_test_fixture():
    with prefect_test_harness():
        yield

def test_my_favorite_function():
    assert my_favorite_function().result() == 42
```
