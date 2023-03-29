---
description: Learn about writing tests for Prefect flows and tasks.
tags:
    - testing
    - unit test
    - development
---

# Testing

Once you have some awesome flows, you probably want to test them!

## Unit testing flows

Prefect provides a simple context manager for unit tests that allows you to run flows and tasks against a temporary local SQLite database.

```python
from prefect import flow
from prefect.testing.utilities import prefect_test_harness

@flow
def my_favorite_flow():
    return 42

def test_my_favorite_flow():
  with prefect_test_harness():
      # run the flow against a temporary testing database
      assert my_favorite_flow() == 42 
```

For more extensive testing, you can leverage `prefect_test_harness` as a fixture in your unit testing framework. For example, when using `pytest`:

```python
from prefect import flow
import pytest
from prefect.testing.utilities import prefect_test_harness

@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield

@flow
def my_favorite_flow():
    return 42

def test_my_favorite_flow():
    assert my_favorite_flow() == 42
```

!!! note Session scoped fixture
    In this example, the fixture is scoped to run once for the entire test session. In most cases, you will not need a clean database for each test and just want to isolate your test runs to a test database. Creating a new test database per test creates significant overhead, so we recommend scoping the fixture to the session. If you need to isolate some tests fully, you can use the test harness again to create a fresh database.

## Unit testing tasks

To test an individual task, you can access the original function using `.fn`:

```python
from prefect import flow, task

@task
def my_favorite_task():
    return 42

@flow
def my_favorite_flow():
    val = my_favorite_task()
    return val

def test_my_favorite_task():
    assert my_favorite_task.fn() == 42
```