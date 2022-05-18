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

# Testing

Now that you have all of these awesome flows, you probably want to test them!

## Unit testing flows

Prefect provides a simple context manager for unit tests that allows you to run flows and tasks against a temporary local SQLite database.

```python
from prefect import flow
from prefect.utilities.testing import prefect_test_harness

@flow
def my_favorite_flow():
    return 42

def test_my_favorite_flow():
  with prefect_test_harness():
      # run the flow against a temporary testing database
      assert my_favorite_function().result() == 42
```

For more extensive testing, you can leverage `prefect_test_harness` as a fixture in your unit testing framework. For example, when using `pytest`:

```python
import pytest
from prefect.utilities.testing import prefect_test_harness

from my_flows import my_favorite_flow

@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield

def test_my_favorite_flow():
    assert my_favorite_flow().result() == 42
```

!!! note Session scoped fixture
    In this example, the fixture is scoped to run once for the entire test session. In most cases, you will not need a clean database for each test and just want to isolate your test runs to a test database. Creating a new test database per test creates significant overhead, so we recommend scoping the fixture to the session. If you need to isolate some tests fully, you can use the test harness again to create a fresh database.

## Unit testing tasks

To test an individual task, you can create a flow inside of your test:

```python
from prefect import flow, task

@task
def my_favorite_task():
    return 42

def test_my_favorite_task():
    @flow
    def my_flow():
        return my_favorite_task()
    
    task_state = my_flow().result()
    assert task_state.result() == 42
```

Alternatively, if your task doesn't use any Prefect behavior, you can test the underlying function using `.fn()`:

```python
from my_tasks import my_favorite_task

def test_my_favorite_task():
    assert my_favorite_task.fn() == 42
```