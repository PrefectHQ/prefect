---
sidebarDepth: 0
---

## Local Debugging

Whether you're running Prefect locally with `Flow.run()` or experimenting with your ideas before putting them into production with Prefect Cloud, Prefect provides you with a wealth of tools for debugging your flows and diagnosing issues.

### Use a FlowRunner for stateless execution

If your problem is related to retries, or if you want to run your flow off-schedule, you might first consider rerunning your flow with `run_on_schedule=False`. This can be accomplished via environment variable (`PREFECT__FLOWS__RUN_ON_SCHEDULE=false`) or keyword (`flow.run(run_on_schedule=False)`). If you instead want to implement a single Flow run yourself consider using a `FlowRunner` directly:

```python
from prefect.engine.flow_runner import FlowRunner

# ... your flow construction

runner = FlowRunner(flow=my_flow)
flow_state = runner.run(return_tasks=my_flow.tasks)
```

This will execute your flow immediately, regardless of its schedule. Note that by default a `FlowRunner` does not provide any individual _task_ states, so if you want that information you must request it with the `return_tasks` keyword argument.

### Choice of Executor

#### `LocalExecutor`

Your choice of executor is very important for how easily it will be to debug your flow. The `DaskExecutor` relies on multiprocessing and multithreading, which can be tricky to navigate. Things like shared state and print statements that disappear into the void can be a real nuisance when trying to figure out what's wrong. Luckily, Prefect provides a `LocalExecutor` that is the most stripped down executor possible - all tasks are executed immediately (in the appropriate order of course) and in your main process.

To swap out executors, follow the schematic:

```python
from prefect.executors import LocalExecutor

# ... your flow construction

state = flow.run(executor=LocalExecutor()) # <-- the executor needs to be initialized
```

and you're set! The `executor` keyword can also be provided to the `FlowRunner.run` method.

#### `LocalDaskExecutor`

If you want to upgrade to a more powerful executor but still maintain an easily debuggable environment, we recommend the `LocalDaskExecutor`. This executor _does_ defer computation using `dask`, but avoids any parallelism, making for an execution pipeline which is easier to reason about.  You can turn parallelism on by providing either `scheduler="threads"` or `scheduler="processes"` when initializing this executor.

!!! tip Prefect defaults
    You can set the `LocalDaskExecutor` to be the default executor on your local machine. To change your Prefect settings (including the default executor), you can either:

    - modify your `~/.prefect/config.toml` file
    - update your OS environment variables; every value in the config file can be overridden by setting `PREFECT__SECTION__SUBSECTION__KEY`. For example, to change the default executor, you can set `PREFECT__ENGINE__EXECUTOR__DEFAULT_CLASS="prefect.executors.LocalExecutor"`

#### `DaskExecutor`

Lastly, if your issue is actually related to parallelism, you'll _need_ to use
the `DaskExecutor`. By default prefect silences the Dask logs, to reenable
them, pass `debug=True`.

### Raising Exceptions in realtime

Sometimes, you don't want Prefect's robust error-handling mechanisms to trap exceptions -- you'd rather they were raised so you could immediately debug them yourself! Use the `raise_on_exception` context manager to raise errors the _moment_ they happen:

```python
from prefect import Flow, task
from prefect.utilities.debug import raise_on_exception


@task
def div(x):
    return 1 / x

with Flow("My Flow") as f:
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
      9 with Flow("My Flow") as f:


ZeroDivisionError: division by zero
```

You can now use your favorite debugger to drop into the traceback and proceed as you normally would.

Note that this utility doesn't require you know anything about where the error occurred.

### Re-raising Execeptions post-hoc

Suppose you want to let the full pipeline run and don't want to raise the trapped error at runtime. Assuming your error was trapped and placed in a `Failed` state, the full exception is stored in the `result` attribute of the task state. Knowing this, you can re-raise it locally and debug from there!

To demonstrate:

```python
from prefect import Flow, task


@task
def gotcha():
    tup = ('a', ['b'])
    try:
        tup[1] += ['c']
    except TypeError:
        assert len(tup[1]) == 1


flow = Flow(name="tuples", tasks=[gotcha])

state = flow.run()
state.result # {<Task: gotcha>: Failed("Unexpected error: AssertionError()")}

failed_state = state.result[gotcha]
raise failed_state.result

---------------------------------------------------------------------------

TypeError                                 Traceback (most recent call last)

<ipython-input-50-8efcdf8dacda> in gotcha()
      7     try:
----> 8         tup[1] += ['c']
      9     except TypeError:

TypeError: 'tuple' object does not support item assignment

During handling of the above exception, another exception occurred:

AssertionError                            Traceback (most recent call last)
<ipython-input-1-f0f986d2f159> in <module>
     22
     23 failed_state = state.result[gotcha]
---> 24 raise failed_state.result

~/Developer/prefect/src/prefect/engine/runner.py in inner(self, state, *args, **kwargs)
     58
     59         try:
---> 60             new_state = method(self, state, *args, **kwargs)
     61         except ENDRUN as exc:
     62             raise_end_run = True

~/Developer/prefect/src/prefect/engine/task_runner.py in get_task_run_state(self, state, inputs, timeout_handler)
    697             self.logger.info("Running task...")
    698             timeout_handler = timeout_handler or main_thread_timeout
--> 699             result = timeout_handler(self.task.run, timeout=self.task.timeout, **inputs)
    700
    701         # inform user of timeout

~/Developer/prefect/src/prefect/utilities/executors.py in multiprocessing_timeout(fn, timeout, *args, **kwargs)
     68
     69     if timeout is None:
---> 70         return fn(*args, **kwargs)
     71     else:
     72         timeout_length = timeout.total_seconds()

<ipython-input-1-f0f986d2f159> in gotcha()
      9         tup[1] += ['c']
     10     except TypeError:
---> 11         assert len(tup[1]) == 1
     12
     13

AssertionError:

%debug # using the IPython magic method to start a pdb session
```

    ipdb> tup
    ('a', ['b', 'c'])
    ipdb> exit

Ah ha! That's what we get for placing mutable objects inside a tuple!

### Fixing your broken Flows

So far we've touched on how to _identify_ your bugs, but how do you fix your broken flow? One way is to re-run the logic that creates the flow from scratch. In production, having a single source of truth for how to create your flow is probably a great idea. However, when iterating quickly or trying to build a proof-of-concept, this can be frustrating.

There are two flow methods that come in handy when trying to update your flow:

- `flow.get_tasks` for retrieving the tasks that satisfy certain conditions
- `flow.replace` once you're ready to replace a task with an updated / fixed version

Using our silly flow from above, let's define a new task and swap it out using these methods:

```python
@task
def fixed():
    tup = ('a', ('b',))
    try:
        tup[1] += ('c',)
    except TypeError:
        assert len(tup[1]) == 1


broken = flow.get_tasks(name="gotcha")[0]
flow.replace(broken, fixed)

flow.run() # Success("All reference tasks succeeded.")
```

If we have a complex dependency graph, `flow.replace` can be a real timesaver for quickly swapping out tasks while preserving all their dependencies!

!!! warning Call Signatures
    Note that `flow.replace` preserves edges - this means the old and new tasks need to have the exact same call signature.
:::


### Resuming failing Flows 

Sometimes flows fail, and so it can be useful to interactively debug them from the command line.  The Prefect API provides a number of different ways of achieving this:

#### Manually mocking out long-running successful tasks

The following Flow fails at run-time due to a `ZeroDivisionError` in the `failure` task

```python
from time import sleep

import prefect
from prefect import Flow, task
from prefect.engine import FlowRunner

@task
def i_will_take_forever() -> int:
    sleep(3)
    return 42


@task
def failure(a_number: int):
    return a_number / 0


with Flow("Success/Failure") as flow:

    a_great_number = i_will_take_forever()
    failure(a_great_number)
    
```

Running this flow in an `iPython` command shell fails

```python
flow.run()
```

Swapping out `1/0` with `1/1` in the task `failure()` using `flow.replace` would fix this error, however, rerunning the whole flow including the slow `i_will_take_forever` is unncessary.  

Every time a Prefect flow is run, the `state` of the flow after it is run is returned.  The flow run `state` result is a dictionary whose keys are `Task` objects and whose values are the states of those tasks after the run is complete.  

```python
from prefect.engine.state import Success

long_task = flow.get_tasks(name="i_will_take_forever")[0]
task_states =  {long_task : Success("Mocked success", result=42)}

flow.run(task_states=task_states)
```

We can access our long-running task using the convenient `get_tasks` method, and then set it's `state` to `Success` via a `task_states` dictionary which can be passed as an argument to `flow.run`.  As a result the flow skips the slow task and resumes from failure.


### Locally check your Flow's `Docker` storage

Another reason a flow might unexpectedly break in production (or fail to run at all) is if its storage is broken (e.g., if you forget a Python dependency in defining your `Docker` storage for the flow). Luckily, checking your flow's storage locally is easy! Let's walk through an example:

```python
from prefect import task, Flow
from prefect.storage import Docker


# import a non-prefect package used for scraping reddit
import praw


@task
def whoami():
    reddit = praw.Reddit(client_id='SI8pN3DSbt0zor',
                         client_secret='xaxkj7HNh8kwg8e5t4m6KvSrbTI',
                         password='1guiwevlfo00esyy',
                         user_agent='testscript by /u/fakebot3',
                         username='fakebot3')
    return reddit.user.me()


storage = Docker(base_image="python:3.7", registry_url="http://my.personal.registry")
flow = Flow("reddit-flow", storage=storage, tasks=[whoami])
```

If you were to deploy this Flow to Cloud, you wouldn't hear from it again. Why? Let's find out - first, build the `Docker` storage locally _without_ pushing to a registry:

```python
# note that this will require either a valid registry_url, or no registry_url
# push=False is important here; otherwise your local image will be deleted
built_storage = flow.storage.build(push=False)
```

Note the Image ID contained in the second to last line of Docker output:

```
Successfully built 0f3b0851148b # your ID will be different
```

Now we have a Docker container on our local machine which contains our flow. To access it, we first identify where the flow is stored:

```python
built_storage.flows
# {"reddit-flow": "/root/.prefect/reddit-flow.prefect"}
```

and then connect to the container via:

```
# connect to an interactive python session running in the container
docker run -it 0f3b0851148b python
```

Finally, we can use `cloudpickle` to deserialize the file into a `Flow` object:

```python
import cloudpickle


with open("/root/.prefect/reddit-flow.prefect", "rb") as f:
    flow = cloudpickle.load(f)
```

Which will result in a very explicit traceback!

```
Traceback (most recent call last):
    flow = cloudpickle.loads(decrypted_pickle)
  File "/usr/local/lib/python3.7/site-packages/cloudpickle/cloudpickle.py", line 944, in subimport
    __import__(name)
ModuleNotFoundError: No module named 'praw'
```

In this particular case, we forgot to include `praw` in our `python_dependencies` for the `Docker` storage; in general, this is one way to ensure your Flow makes it through the deployment process uncorrupted.

!!! tip The More You Know
    We actually found this process to be so useful, we've automated it for you! Prefect now performs a "health check" prior to pushing your Docker image, which essentially runs the above code and ensures your Flow is deserializable inside its container. However, the mechanics by which this occurs is still useful to know.
