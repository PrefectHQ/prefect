---
title: 'PIN-5: Combining Tasks'
sidebarDepth: 0
---

# PIN-5: Combining Tasks

Date: 2019-02-20

Author: Chris White

## Status

Declined (_see bottom of page for reason_)

## Context

Imagine the following typical scenario: a data engineer wants to create a Prefect Flow that routinely migrates some data from S3 to Google Cloud Storage (along with other things). In our current framework, we implicitly recommend the user do something like (pseudo-code):

```python
s3_task = S3Task(..)
gcs_task = GCSTask(...)

with Flow("migration") as f:
    gcs_task(data=s3_task)
```

This is OK, but imagine the S3 Task returns 10 GB of data, and the user's default settings are to use "checkpointing". In this case, the data coming out of S3 will hit the checkpoint, be shipped off somewhere else (dragging this Flow down), and then have to move around the Dask workers, resulting in large and unnecessary data movement. Moreover, many of these infrastructure / db clients have hooks for large data streams that we can't take advantage of with this setup.

Another option is for the user to re-implement all the hooks / credentials / etc. for _both_ GCS and S3, resulting in a monster `S3toGCSTask`. With this pattern, if we have M sources and N sinks, we need to maintain and test M\*N different tasks (this is what frameworks like Airflow currently do). We want to avoid this situation. Ideally we should only have to maintain M + N tasks that can be flexibly and powerfully composed in various ways.

Additionally, it would be nice if users could specify that two tasks should run on the same worker, in the same process, and share memory.

## Proposal

We will implement some sugar that allows users to combine two tasks into a single `Task`. For example, the imperative version of this might look like (pseudo-code):

```python
class CombinedTask(Task):
    def __init__(self, first_task: Task, second_task: Task, stitch_function: Callable):
        self.first_task = first_task
        self.second_task = second_task
        self.stitch_function = stitch_function

    def run(self):
        inputs = self.first_task.run()
        processed = self.stitch_function(inputs)
        result = self.second_task.run(**processed)
        return result
```

along with a functional method on Task objects:

```python
second_task.combine(first_task, **additional_kwargs, stitch_function=stitch_function)
```

Of course, there is some work that needs to be done under the hood to match inputs / outputs, and allow for calling patterns such as

```python
second_task.combine(first_task(config="some_setting"), parameter="another_input")
```

But ultimately, these two tasks would be combined into a _single task_ that is submitted to a _single worker_.

### How many tasks?

This PIN proposes we only support combining _two_ tasks, with our target use case being migrating data. Allowing for arbitrary numbers might encourage an anti-pattern (Prefect generally _prefers_ small, modular tasks), and become a headache to maintain (deciding which arguments to a combined task should actually be combined vs. left as standalone tasks will be tricky).

## Consequences

The largest user-facing consequence is that, if a user uses this pattern, they lose any prefect hooks which may occur between the two tasks, such as trigger checks, notifications, state handlers, etc. In my view, this is perfectly OK in certain situations such as this, where the goal is to _move_ data. If something fails, the data is still sitting in S3, and the user just needs the error to debug.

Exposing this pattern to users will certainly appease many of the data engineers we've talked to, as well as reduce the load on our system. Additionally, it would allow us to utilize a shared (temporary) filesystem for these connected / combined tasks and connect to different hooks that otherwise wouldn't be available to us.

## Actions

### Reason for declining

Designing simple syntax for creating combined tasks off-the-shelf proved to be overly complicated. Tracking all the necessary input dependencies, and knowing which tasks needed to be combined started to run into recreating a "sub-flow" for the two tasks. Given this, we have decided not to provide sugar for this construction, but instead write clear documentation for how to build individual "combined" tasks for individual use cases. We might revisit this "sub-flow" idea in the future, but are tabling it for now.
