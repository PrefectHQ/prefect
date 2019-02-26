---
sidebarDepth: 0
---

## Local Debugging

::: tip Practice Makes Prefect
A notebook containing all code presented in this tutorial can be downloaded [here](/notebooks/local-debugging.ipynb).
:::

Oftentimes you want to experiment with your ideas before putting them into production; moreover, when something unexpected happens you need an efficient way of diagnosing what went wrong. Prefect provides you with a wealth of tools for debugging your flows locally and diagnosing issues.

### Choice of Executor

#### `LocalExecutor`

Your choice of executor is very important for how easily it will be to debug your flow. The `DaskExecutor` relies on multiprocessing and multithreading, which can be tricky to navigate. Things like shared state and print statements that disappear into the void can be a real nuisance when trying to figure out what's wrong. Luckily, Prefect provides a `LocalExecutor` which is the most stripped down executor possible - all tasks are executed immediately (in the appropriate order of course) and in your main process.

To swap out executors, simply follow the schematic:

```python
from prefect.engine.executors import LocalExecutor

# ... your flow construction

state = flow.run(executor=LocalExecutor()) # <-- the executor needs to be initialized
```

and you're set!

#### `SynchronousExecutor`

If you want to upgrade to a more powerful executor but still maintain an easily debuggable environment, we recommend the `SynchronousExecutor`. This executor _does_ defer computation using `dask`, but avoids any parallelism, making for an execution pipeline which is easier to reason about.

::: tip Prefect defaults
The `SynchronousExecutor` is the default executor on your local machine; in production, the `DaskExecutor` will be the default. To change your Prefect settings (including the default executor), you can either:

- modify your `~/.prefect/config.toml` file
- update your OS environment variables; every value in the config file can be overriden by setting `PREFECT__SECTION__SUBSECTION__KEY`. For example, to change the default executor, you can set `PREFECT__ENGINE__EXECUTOR="prefect.engine.executors.LocalExecutor"`
  :::

#### `DaskExecutor`

Lastly, if your issue is actually related to parallelism, you'll _need_ to use the `DaskExecutor`. There are two initialization keyword arguments that are useful to know about when debugging:

- `processes`, which is a boolean specifying whether you want to use multiprocessing or not. The default for this flag is `False`. Try toggling it to see if your issue is related to multiprocessing or multithreading!
- `debug`, which is another boolean for setting the logging level of `dask.distributed`; the default value is set from your Prefect configuration file and should be `True` to get the most verbose output from `dask`'s logs.

### Raising Exceptions in realtime

Sometimes, you don't want Prefect's robust error-handling mechanisms to trap exceptions -- you'd rather they were raised so you could immediately debug them yourself! Use the `raise_on_exception` context manager to raise errors the _moment_ they happen:

```python
from prefect import Flow, task
from prefect.utilities.debug import raise_on_exception


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
::: tip
Note that this utility doesn't require you know anything about where the error occured.
:::

### Re-raising Execeptions post-hoc

Suppose you want to let the full pipeline run and don't want to raise the trapped error at runtime. Assuming your error was trapped and placed in a `Failed` state, the full exception is stored in the `result` attribute of the task state. Knowing this, you can re-raise it locally and debug from there!
::: tip Knowing what failed
Sometimes, you aren't immediately sure which task(s) failed. Because `flow.run()` doesn't return any task states by default, you might wonder how to get the correct task state to inspect the error message. Prefect provides a convenient debug `state_handler` that will return any tasks which failed during execution so you don't have to know which to request beforehand! (Note: this state handler only works with the `LocalExecutor`)
:::

To demonstrate:

```python
from prefect import Flow, task
from prefect.utilities.debug import make_return_failed_handler


@task
def gotcha():
    tup = ('a', ['b'])
    try:
        tup[1] += ['c']
    except TypeError:
        assert len(tup[1]) == 1


flow = Flow(tasks=[gotcha])

# here, we use a special state_handler to automatically populate the `return_tasks` set.
return_tasks = set()
state = flow.run(
    return_tasks=return_tasks,
    task_runner_state_handlers=[make_return_failed_handler(return_tasks)])
state.result # {<Task: gotcha>: Failed("Unexpected error")}

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

### Locally check your Flow's environment

Another reason a Flow might unexpectedly break in production (or fail to run at all) is if its environment is broken (e.g., if you forget a Python dependency in defining your `DockerEnvironment` for the Flow).  Luckily, checking `DockerEnvironment`s locally is easy!  Let's walk through an example:

```python
from prefect import task, Flow
from prefect.environments import DockerEnvironment

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


env = DockerEnvironment(base_image="python:3.6", registry_url="http://my.personal.registry")
flow = Flow("reddit-flow", environment=env, tasks=[whoami])
```

If you were to deploy this Flow to Cloud, you wouldn't hear from it again.  Why?  Let's find out - first, build the `DockerEnvironment` locally _without_ pushing to a registry:

```python
# note that this will require either a valid registry_url, or no registry_url
# push=False is important here; otherwise your local image will be deleted
built_env = env.build(flow, push=False)
```

Note the Image ID contained in the second to last line of Docker output:

```
Successfully built 0f3b0851148b # your ID will be different
```

Now we have a Docker container on our local machine which contains a `LocalEnvironment` containing our flow. To access it, we simply connect to the container via:

```
# connect to an interactive python session running in the container
docker run -it 0f3b0851148b python
```

and then load the environment from a file:

```python
from prefect.environments import from_file

local_env = from_file('/root/.prefect/flow_env.prefect')
flow = local_env.deserialize_flow_from_bytes(local_env.serialized_flow)
```

Which will result in a very explicit traceback!

```
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/usr/local/lib/python3.6/site-packages/prefect/environments.py", line 167, in deserialize_flow_from_bytes
    flow = cloudpickle.loads(decrypted_pickle)
  File "/usr/local/lib/python3.6/site-packages/cloudpickle/cloudpickle.py", line 944, in subimport
    __import__(name)
ModuleNotFoundError: No module named 'praw'
```

In this particular case, we forgot to include `praw` in our `python_dependencies` for the `DockerEnvironment`; in general, this is one way to ensure your Flow makes it through the deployment process uncorrupted.
