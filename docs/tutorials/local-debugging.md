---
sidebarDepth: 0
---

## Local Debugging

Oftentimes you want to experiment with your ideas before putting them into production; moreover, when something unexpected happens you need an efficient way of diagnosing what went wrong.  Prefect provides you with a wealth of tools for debugging your flows locally and diagnosing issues.

### Choice of Executor

#### `LocalExecutor` 
Your choice of executor is very important for how easily it will be to debug your flow.  The `DaskExecutor` relies on multiprocessing and multithreading, which can be tricky to navigate.  Things like shared state and print statements that disappear into the void can be a real nuisance when trying to figure out what's wrong.  Luckily, Prefect provides a `LocalExecutor` which is the most stripped down executor possible - all tasks are executed immediately (in the appropriate order of course) and in your main process.

To swap out executors, simply follow the schematic:
```python
from prefect.engine.executors import LocalExecutor

# ... your flow construction

state = flow.run(executor=LocalExecutor()) # <-- the executor needs to be initialized
```
and you're set!  

#### `SynchronousExecutor`
If you want to upgrade to a more powerful executor but still maintain an easily debuggable environment, we recommend the `SynchronousExecutor`.  This executor _does_ defer computation using `dask`, but avoids any parallelism, making for an execution pipeline which is easier to reason about.

::: tip Synchronous is the local default
The `SynchronousExecutor` is the default executor on your local machine; in production, the `DaskExecutor` will be the default.
:::
#### `DaskExecutor`

Lastly, if your issue is actually related to parallelism, you'll _need_ to use the `DaskExecutor`.  There are two initialization keyword arguments that are useful to know about when debugging:
- `processes`, which is a boolean specifying whether you want to use multiprocessing or not.  The default for this flag is `False`.  Try toggling it to see if your issue is related to multiprocessing or multithreading!
- `debug`, which is another boolean for setting the logging level of `dask.distributed`; the default value is set from your Prefect configuration file and should be `True` to get the most verbose output from `dask`'s logs.


### Raising Exceptions in realtime

Sometimes, you don't want Prefect's robust error-handling mechanisms to trap exceptions -- you'd rather they were raised so you could immediately debug them yourself! Use the `raise_on_exception` context manager to raise errors the _moment_ they happen:


```python
from prefect import Flow, task
from prefect.utilities.tests import raise_on_exception


@task
def div(x):
    return 1 / x

with Flow() as f:
    val = div(0)
    
with raise_on_exception():
    f.run()

---------------------------------------------------------------------------

ZeroDivisionError                         Traceback (most recent call last)

<ipython-input-1-82c40dd24406> in <module>()
     11 
     12 with raise_on_exception():
---> 13     f.run()


... # the full traceback is long

<ipython-input-1-82c40dd24406> in div(x)
      5 @task
      6 def div(x):
----> 7     return 1 / x
      8 
      9 with Flow() as f:


ZeroDivisionError: division by zero
```

You can now use your favorite debugger to drop into the traceback and proceed as you normally would.

### Re-raising Execeptions post-hoc

Suppose you _are_ in production and don't want to raise the trapped error at runtime.  Assuming your error was trapped and placed in a `Failed` state, the full exception is stored in the `message` attribute of the task state.  Knowing this, you can re-raise it locally and debug from there!  To demonstrate:


```python
from prefect import Flow, task


@task
def gotcha():
    tup = ('a', ['b'])
    try:
        tup[1] += ['c']
    except TypeError:
        assert len(tup[1]) == 1
        

flow = Flow(tasks=[gotcha])
state = flow.run(return_tasks=[gotcha])
state.result # {<Task: gotcha>: Failed("")}, not very informative

failed_state = state.result[gotcha]
raise failed_state.message

---------------------------------------------------------------------------

TypeError                                 Traceback (most recent call last)

<ipython-input-50-8efcdf8dacda> in gotcha()
      7     try:
----> 8         tup[1] += ['c']
      9     except TypeError:


TypeError: 'tuple' object does not support item assignment


During handling of the above exception, another exception occurred:


AssertionError                            Traceback (most recent call last)

<ipython-input-50-8efcdf8dacda> in <module>()
     16 
     17 failed_state = state.result[gotcha]
---> 18 raise failed_state.message

...

<ipython-input-50-8efcdf8dacda> in gotcha()
      8         tup[1] += ['c']
      9     except TypeError:
---> 10         assert len(tup[1]) == 1
     11 
     12 


AssertionError: 

%debug # using the IPython magic method to start a pdb session
```
    ipdb> tup
    ('a', ['b', 'c'])
    ipdb> exit


Ah ha! That's what we get for placing mutable objects inside a tuple!

### Fixing your broken Flows

So far we've touched on how to _identify_ your bugs, but how do you fix your broken flow?  One way is to re-run the logic that creates the flow from scratch.  In production, having a single source of truth for how to create your flow is probably a great idea.  However, when iterating quickly or trying to build a proof-of-concept, this can be frustrating.

There are two flow methods that come in handy when trying to update your flow:
- `flow.get_tasks` for retrieving the tasks that satisfy certain conditions
- `flow.replace` once you're ready to replace a task with an updated / fixed version

Using our silly flow from above, let's define a new task and swap it out using these methods:


```python
@task
def fixed():
    tup = ('a', ('b'))
    try:
        tup[1] += ('c')
    except TypeError:
        assert len(tup[1]) == 1
        
        
broken = flow.get_tasks(name="gotcha")[0]
flow.replace(broken, fixed)

flow.run() # Success("All reference tasks succeeded.")
```

If we have a complex dependency graph, `flow.replace` can be a real timesaver for quickly swapping out tasks while preserving all their dependencies!

::: warning Call Signatures
Note that `flow.replace` preserves edges - this means the old and new tasks need to have the exact same call signature.
:::
