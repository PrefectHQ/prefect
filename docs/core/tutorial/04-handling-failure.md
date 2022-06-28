---
sidebarDepth: 0
---

# Handling Failure

!!! tip Follow along in the Terminal

    ```
    cd examples/tutorial
    python 04_handle_failures.py
    ```



## If at first you don't succeed...

Now that we have a [working ETL flow](/core/tutorial/03-parameterized-flow.html) let's take further steps to ensure its robustness. The `extract_*` tasks are making web requests to external APIs in order to fetch the data. What if the API is unavailable for a short period? Or if a single request times out for unknown reasons? **Prefect `Tasks` can be retried on failure**; let's add this to our `extract_*` tasks:

```python{1,6,12}
from datetime import timedelta
import aircraftlib as aclib
from prefect import task, Flow, Parameter


@task(max_retries=3, retry_delay=timedelta(seconds=10))
def extract_reference_data():
    # same as before ...
    ...


@task(max_retries=3, retry_delay=timedelta(seconds=10))
def extract_live_data(airport, radius, ref_data):
    # same as before ...
    ...
```

This is a simple measure that helps our `Flow` gracefully handle transient errors in only the tasks we specify. Now if there are any failed web requests, a maximum of 3 attempts will be made, waiting 10 seconds between each attempt.

!!! tip More Ways to Handle Failures
    There are other mechanisms Prefect provides to enable specialized behavior around failures:

    - [**Task Triggers**](/core/concepts/execution.html#triggers): selectively execute `Tasks` based on the states from upstream `Task` runs.
    - [**State Handlers**](/core/concepts/states.html#state-handlers-callbacks): provide a Python function that is invoked whenever a `Flow` or `Task` changes state - see all the things!
    - [**Notifications**](/core/concepts/notifications.html): Get [Slack notifications](/core/advanced_tutorials/slack-notifications.html#slack-notifications) upon state changes of interest or use the [EmailTask](/api/latest/tasks/notifications.html#emailtask) in combination with Task Triggers.



Up Next! Schedule our Flow to run periodically or on a custom schedule.
