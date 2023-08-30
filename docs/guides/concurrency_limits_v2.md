---
description: Learn how to control concurrency and apply rate limits using Prefect's provided utilities.
tags:
    - concurrency
    - rate limits
search:
  boost: 2
---

# Concurrency Limits and Rate Limits

Concurrency limits allow you to manage task execution efficiently, controlling how many tasks run simultaneously. They are ideal when optimizing resource usage, preventing bottlenecks, and customizing task execution are priorities.

Rate limits ensure system stability by governing the frequency of requests or operations. They are suitable for preventing overuse, ensuring fairness, and handling errors gracefully.

When selecting between concurrency and rate limits, consider your primary goal. Choose concurrency limits for resource optimization and task management. Choose rate limits to maintain system stability and fair access to services.

## Managing concurrency limits and rate limits

TK Something about how to manage concurrency limits and rate limits in the UI
TK Something about the difference between an active limit and an inactive limit.
TK Description of slot decay

## Using the `concurrency` context manager
The `concurrency` context manager allows control over the maximum number of concurrent operations. You can select either the synchronous (`sync`) or asynchronous (`async`) version, depending on your use case. Here's how to use it:

!!! tip "Concurrency limits are implicitly created"
    When using the `concurrency` context manager, the concurrency limit you use will be created, in an inactive state, if it does not already exist.

**Sync**

```python
from prefect import flow, task
from prefect.concurrency.sync import concurrency


@task
def process_data(x, y):
    with concurrency("database", occupy=1):
        return x + y


@flow
def my_flow():
    for x, y in [(1, 2), (2, 3), (3, 4), (4, 5)]:
        process_data.submit(x, y)


if __name__ == "__main__":
    my_flow()
```


**Async**

```python
import asyncio
from prefect import flow, task
from prefect.concurrency.asyncio import concurrency


@task
async def process_data(x, y):
    async with concurrency("database", occupy=1):
        return x + y


@flow
async def my_flow():
    for x, y in [(1, 2), (2, 3), (3, 4), (4, 5)]:
        await process_data.submit(x, y)


if __name__ == "__main__":
    asyncio.run(my_flow())
```


1. The code imports the necessary modules and the concurrency context manager. Use the `prefect.concurrency.sync` module for sync usage and the `prefect.concurrency.asyncio` module for async usage.
2. It defines a `process_data` task, taking `x` and `y` as input arguments. Inside this task, the concurrency context manager controls concurrency, using the `database` concurrency limit and occupying one slot. If another task attempts to run with the same limit and no slots are available, that task will be blocked until a slot becomes available.
3. A flow named `my_flow` is defined. Within this flow, it iterates through a list of tuples, each containing pairs of x and y values. For each pair, the `process_data` task is submitted with the corresponding x and y values for processing.


## Using `rate_limit`
The rate limit feature provides control over the frequency of requests or operations, ensuring responsible usage and system stability. Depending on your requirements, you can utilize `rate_limit` to govern both synchronous (sync) and asynchronous (async) operations. Here's how to make the most of it:

!!! tip "Slot decay"
    When using the `rate_limit` function, the concurrency limit you use must have a slot decay configured. 

**Sync**

```python
from prefect import flow, task
from prefect.concurrency.sync import rate_limit


@task
def make_http_request():
    rate_limit("rate-limited-api")
    print("Making an HTTP request...")


@flow
def my_flow():
    for _ in range(10):
        make_http_request.submit()


if __name__ == "__main__":
    my_flow()
```


**Async**

```python
import asyncio

from prefect import flow, task
from prefect.concurrency.asyncio import rate_limit


@task
async def make_http_request():
    await rate_limit("rate-limited-api")
    print("Making an HTTP request...")


@flow
async def my_flow():
    for _ in range(10):
        await make_http_request.submit()


if __name__ == "__main__":
    asyncio.run(my_flow())
```

1. The code imports the necessary modules and the concurrency context manager. Use the `prefect.concurrency.sync` module for sync usage and the `prefect.concurrency.asyncio` module for async usage.
2. It defines a `make_http_request` task. Inside this task, the `rate_limit` function ensures that the requests are made at a controlled pace.
3. A flow named `my_flow` is defined. Within this flow the `make_http_request` task is submitted 10 times.

## Using `concurrency` and `rate_limit` outside of a flow

`concurrency` and `rate_limit` can be used outside of a flow to control concurrency and rate limits for any operation. 

```python
import asyncio

from prefect.concurrency.asyncio import rate_limit


async def main():
    for _ in range(10):
        await rate_limit("rate-limited-api")
        print("Making an HTTP request...")



if __name__ == "__main__":
    asyncio.run(main())
```
