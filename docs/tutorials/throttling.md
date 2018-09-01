# Task Throttling <Badge text="advanced" type="warn"/><Badge text="0.4.0+"/>

> Topics covered: _executors_, _parallelism_, _tags_,  _throttling_

Task throttling refers to the ability to constrain how many tasks are allowed to run in parallel.  Some questions we'd like to answer:
- How do we run parallel workflows locally in Prefect?
- Why is task throttling useful?
- How do we tag tasks, and throttle execution per tag?

::: tip
Because we will rely heavily on printing from within Python subprocesses, if you would like to reproduce the code examples here be sure to run them from a terminal-based Python session.  

Additionally, because our examples are very verbose, we have chosen to display stylized images of the output to aid in understanding.
:::

### What and Why

_Throttling_ refers to the ability to control the maximum number of tasks which are allowed to run in parallel.  For example, if you have 10 tasks which don't depend on each other, in theory all 10 tasks could run simultaneously.  However there are many situations in which this is undesireable, e.g., when running up against resource usage limits such as database concurrency limits and API quotas.  In theses situations, we want the ability to cap how many tasks can run simultaneously. Moreover, a single task might have more than one limitation if it accesses multiple resources, in which case we want to be able to _throttle per resource_.  All of these situations are easily handled by Prefect with one or two lines of additional code.

### How

Using task throttling in Prefect is easy - it begins by simply "tagging" all appropriate tasks; this can be done as an initialization keyword or using the `tags` contextmanager to assign tags in groups.  

::: tip An Extended Example
In this tutorial we will walk through an extended example in which we have multiple tasks which print a simple string 10 times; in order to ensure these tasks run for a reasonable amount of time, we include a random delay during the printing.  Moreover, because we will eventually run these tasks inside of [new Python subprocesses](https://docs.python.org/3.4/library/multiprocessing.html), we have to include a `sys.stdout.flush()` line after each call to `print`.

It's also worth noting that the actual execution order of completely independent tasks is non-deterministic so your local results may differ slightly.  If we wanted the order to be deterministic, we'd need to explicitly set upstream / downstream dependencies for the tasks.
:::

```python
from prefect import Flow, tags, task
from time import sleep
import random
import sys

# --------
# assign tags at task creation
# --------

@task(tags=["print"])
def say_hi(name):
    "print `name` 10 times."
    pause_at = random.randint(0, 10)
    for i in range(10):
        if i == pause_at:
            sleep(1)
        print(f'{name} was here')
        sys.stdout.flush()
        
# --------
# or at flow creation
# --------
        
with Flow() as f:
    with tags("example"):
        a = say_hi("alice")
        b = say_hi("bob")
    c = say_hi("chris")

a.tags # {'example', 'print'}
c.tags # {'print'}
```

As we can see, every task constructor accepts an optional `tags` keyword argument (these can be used purely for informational purposes as well).  Moreover, there is a convenient `tags` contextmanager for assigning tags in batches - using this can make for more readable code.

Next we need to specify which tags we want throttled, and by how much.  This is conveyed with a dictionary of `{tag: throttle_number}`, which can be provided in two places:
- *at flow initialization*: this is best when the throttling is an intrinsic part of the flow that should be the default behavior anytime the flow is run.  In code, this would look like:
```python
with Flow(throttle={'print': 1}) as f:
    ...
```
- *at flow runtime*: which is what we will be doing for the sake of experimentation:
```python
f.run(throttle={'print': 1})
```
::: warning Throttling is an upper bound
To be clear, the throttle number you provide for each tag serves as an _upper bound_ on the number of tasks which can be run in parallel; it does not guarantee that ...
:::

Let's run our flow with default settings to see how this flow normally behaves:


```python
f.run()
# Success("All reference tasks succeeded.")

# chris was here
# ... 9 more times ...
# bob was here
# ... 9 more times ...
# alice was here
# ... 9 more times ...
```
Because our example is so verbose, we will refrain from repeating all of the output for every run.  Instead, we will resort to a stylized representation of what was observed.  Our visual representation of the run above is given by:

<img src='/serial.png'>

From the output, it is clear that the `chris` task ran first, followed by the `bob` task and finally the `alice` task.  If they had run in parallel, we would expect to see a random shuffling of names throughout.  Why did this not happen? 

::: tip Locally, Prefect defaults to synchronous execution
When running locally, the default executor (which executes tasks) is the `SynchronousExecutor`, which executes serially.  In order to take advantage of local parallelism we need to use the `DaskExecutor`.
:::

::: warning
By default, the Prefect `DaskExecutor` uses multithreading and not multiprocessing; however, in versions of `distributed` prior to `1.23.0` there was [a small bug in `dask.distributed`](https://github.com/dask/distributed/issues/2220) which prevented throttling from working in multithreaded mode.  Consequently, to use throttling locally on older versions of `distributed` you'll need to set `processes=True` in the `DaskExecutor`.
:::

To use an executor other than the default, simply import it, initialize it, and provide it to your flow's `run()` method:


```python
from prefect.engine.executors import DaskExecutor

f.run(executor=DaskExecutor(processes=True))
# Success("All reference tasks succeeded.")
```
<img src='/parallel.png'>

Voila! Now we have all three tasks printing at the same time!  This is great, but can be a little confusing with everyone speaking over each other; let's use throttling to only allow one person to speak at a time by throttling the `"print"` tag to an extreme value of 1:


```python
f.run(executor=DaskExecutor(processes=True), throttle={'print': 1})
# Success("All reference tasks succeeded.")
```
<img src='/parallel-throttle.png'>

Nice! Of course, we could use any number as a throttle value:


```python
f.run(executor=DaskExecutor(processes=True), throttle={'print': 2})
# Success("All reference tasks succeeded.")
```

<img src='/parallel-less.png'>

All tasks have been throttled in our examples so far, but we can be more nuanced in our application of throttling.  In most situations people are OK with chris talking anytime he wants; however, alice and bob shouldn't talk over each other.  Easy!  Recall that we tagged alice and bob as `"example"` previously, whereas chris was only tagged `"print"`.  To achieve this we can throttle the `"example"` tasks and leave all `"print"` tasks unthrottled as a group:


```python
f.run(executor=DaskExecutor(processes=True), throttle={'example': 1})
# Success("All reference tasks succeeded.")
```
<img src='/parallel-throttle-sub.png'>

### Advanced Usage

Extending these examples, Prefect allows for arbitrarily many tags to be throttled, and for arbitrarily many tags to be placed on a single task. Consequently, we can orchestrate complicated workflows without fear that our resources will be overused.

In the following example, we will have three tags and five tasks which we will throttle in different ways:

```python
with Flow() as big_flow:
    with tags("group C"):
        a = say_hi("alice")
        b = say_hi("bob")
    with tags("group B"):
        c = say_hi("chris")
        with tags("group A"):
            d = say_hi("jeremiah")
            e = say_hi("josh")
            
e.tags # {"group A", "group B", "group C"}

# --------
# run the flow
# --------

big_flow.run(executor=DaskExecutor(processes=True),
             throttle={'group A': 1, 'group B': 2, 'group C': 1})
# Success("All reference tasks succeeded.")
```

<img src='/multi-tag-throttle.png'>

