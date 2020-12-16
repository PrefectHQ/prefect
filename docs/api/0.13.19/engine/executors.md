---
sidebarDepth: 2
editLink: false
---
# Executors
---
Prefect Executors implement the logic for how Tasks are run. The standard interface
for an Executor consists of the following methods:

- `submit(fn, *args, **kwargs)`: submit `fn(*args, **kwargs)` for execution;
    note that this function is (in general) non-blocking, meaning that `executor.submit(...)`
    will _immediately_ return a future-like object regardless of whether `fn(*args, **kwargs)`
    has completed running
- `wait(object)`: resolves any objects returned by `executor.submit` to
    their values; this function _will_ block until execution of `object` is complete

Currently, the available executor options are:

- `LocalExecutor`: the no frills, straightforward executor - great for debugging;
    tasks are executed immediately upon being called by `executor.submit()`.Note
    that the `LocalExecutor` is not capable of parallelism.  Currently the default executor.
- `LocalDaskExecutor`: an executor that runs on `dask` primitives with a
    configurable dask scheduler.
- `DaskExecutor`: the most feature-rich of the executors, this executor runs
    on `dask.distributed` and has support for multiprocessing, multithreading, and distributed execution.

Which executor you choose depends on whether you intend to use things like parallelism
of task execution.

The key difference between the `LocalDaskExecutor` and the `DaskExecutor` is the choice
of scheduler. The `LocalDaskExecutor` is configurable to use
[any number of schedulers](https://docs.dask.org/en/latest/scheduler-overview.html) while the
`DaskExecutor` uses the [distributed scheduler](https://docs.dask.org/en/latest/scheduling.html).
This means that the `LocalDaskExecutor` can help achieve some multithreading / multiprocessing
however it does not provide as many distributed features as the `DaskExecutor`.
 ## Executor
 <div class='class-sig' id='prefect-engine-executors-base-executor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.base.Executor</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L7">[source]</a></span></div>

Base Executor class that all other executors inherit from.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-start'><p class="prefect-class">prefect.engine.executors.base.Executor.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L18">[source]</a></span></div>
<p class="methods">Context manager for initializing execution.<br><br>Any initialization this executor needs to perform should be done in this context manager, and torn down after yielding.</p>|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-submit'><p class="prefect-class">prefect.engine.executors.base.Executor.submit</p>(fn, *args, extra_context=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L28">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns a future-like object.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`extra_context (dict, optional)`: an optional dictionary with extra information         about the submitted task     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: a future-like object</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-wait'><p class="prefect-class">prefect.engine.executors.base.Executor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L46">[source]</a></span></div>
<p class="methods">Resolves futures to their values. Blocks until the future is complete.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: iterable of futures to compute</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: an iterable of resolved futures</li></ul></p>|

---
<br>

 ## DaskExecutor
 <div class='class-sig' id='prefect-engine-executors-dask-daskexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor</p>(address=None, cluster_class=None, cluster_kwargs=None, adapt_kwargs=None, client_kwargs=None, debug=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L76">[source]</a></span></div>

An executor that runs all functions using the `dask.distributed` scheduler.

By default a temporary `distributed.LocalCluster` is created (and subsequently torn down) within the `start()` contextmanager. To use a different cluster class (e.g. [`dask_kubernetes.KubeCluster`](https://kubernetes.dask.org/)), you can specify `cluster_class`/`cluster_kwargs`.

Alternatively, if you already have a dask cluster running, you can provide the address of the scheduler via the `address` kwarg.

Note that if you have tasks with tags of the form `"dask-resource:KEY=NUM"` they will be parsed and passed as [Worker Resources](https://distributed.dask.org/en/latest/resources.html) of the form `{"KEY": float(NUM)}` to the Dask Scheduler.

**Args**:     <ul class="args"><li class="args">`address (string, optional)`: address of a currently running dask         scheduler; if one is not provided, a temporary cluster will be         created in `executor.start()`.  Defaults to `None`.     </li><li class="args">`cluster_class (string or callable, optional)`: the cluster class to use         when creating a temporary dask cluster. Can be either the full         class name (e.g. `"distributed.LocalCluster"`), or the class itself.     </li><li class="args">`cluster_kwargs (dict, optional)`: addtional kwargs to pass to the        `cluster_class` when creating a temporary dask cluster.     </li><li class="args">`adapt_kwargs (dict, optional)`: additional kwargs to pass to `cluster.adapt`         when creating a temporary dask cluster. Note that adaptive scaling         is only enabled if `adapt_kwargs` are provided.     </li><li class="args">`client_kwargs (dict, optional)`: additional kwargs to use when creating a         [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client).     </li><li class="args">`debug (bool, optional)`: When running with a local cluster, setting         `debug=True` will increase dask's logging level, providing         potentially useful debug info. Defaults to the `debug` value in         your Prefect configuration.     </li><li class="args">`**kwargs`: DEPRECATED</li></ul> Using a temporary local dask cluster:


```python
executor = DaskExecutor()

```

Using a temporary cluster running elsewhere. Any Dask cluster class should work, here we use [dask-cloudprovider](https://cloudprovider.dask.org):


```python
executor = DaskExecutor(
    cluster_class="dask_cloudprovider.FargateCluster",
    cluster_kwargs={
        "image": "prefecthq/prefect:latest",
        "n_workers": 5,
        ...
    },
)

```

Connecting to an existing dask cluster


```python
executor = DaskExecutor(address="192.0.2.255:8786")

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-start'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L244">[source]</a></span></div>
<p class="methods">Context manager for initializing execution.<br><br>Creates a `dask.distributed.Client` and yields it.</p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-submit'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.submit</p>(fn, *args, extra_context=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L410">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns a Future object.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`extra_context (dict, optional)`: an optional dictionary with extra information         about the submitted task     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul> **Returns**:     <ul class="args"><li class="args">`Future`: a Future-like object that represents the computation of `fn(*args, **kwargs)`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-wait'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L439">[source]</a></span></div>
<p class="methods">Resolves the Future objects to their values. Blocks until the computation is complete.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: single or iterable of future-like objects to compute</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: an iterable of resolved futures with similar shape to the input</li></ul></p>|

---
<br>

 ## LocalDaskExecutor
 <div class='class-sig' id='prefect-engine-executors-dask-localdaskexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.dask.LocalDaskExecutor</p>(scheduler="threads", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L455">[source]</a></span></div>

An executor that runs all functions locally using `dask` and a configurable dask scheduler.

**Args**:     <ul class="args"><li class="args">`scheduler (str)`: The local dask scheduler to use; common options are         "threads", "processes", and "synchronous".  Defaults to "threads".     </li><li class="args">`**kwargs (Any)`: Additional keyword arguments to pass to dask config</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-dask-localdaskexecutor-start'><p class="prefect-class">prefect.engine.executors.dask.LocalDaskExecutor.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L527">[source]</a></span></div>
<p class="methods">Context manager for initializing execution.</p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-localdaskexecutor-submit'><p class="prefect-class">prefect.engine.executors.dask.LocalDaskExecutor.submit</p>(fn, *args, extra_context=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L575">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns a `dask.delayed` object.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`extra_context (dict, optional)`: an optional dictionary with extra         information about the submitted task     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul> **Returns**:     <ul class="args"><li class="args">`dask.delayed`: a `dask.delayed` object that represents the         computation of `fn(*args, **kwargs)`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-localdaskexecutor-wait'><p class="prefect-class">prefect.engine.executors.dask.LocalDaskExecutor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L601">[source]</a></span></div>
<p class="methods">Resolves a (potentially nested) collection of `dask.delayed` object to its values. Blocks until the computation is complete.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: iterable of `dask.delayed` objects to compute</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: an iterable of resolved futures</li></ul></p>|

---
<br>

 ## LocalExecutor
 <div class='class-sig' id='prefect-engine-executors-local-localexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.local.LocalExecutor</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/local.py#L6">[source]</a></span></div>

An executor that runs all functions synchronously and immediately in the main thread.  To be used mainly for debugging purposes.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-local-localexecutor-submit'><p class="prefect-class">prefect.engine.executors.local.LocalExecutor.submit</p>(fn, *args, extra_context=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/local.py#L12">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns the result of the computation.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`extra_context (dict, optional)`: an optional dictionary with extra information         about the submitted task     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the result of `fn(*args, **kwargs)`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-local-localexecutor-wait'><p class="prefect-class">prefect.engine.executors.local.LocalExecutor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/local.py#L30">[source]</a></span></div>
<p class="methods">Returns the results of the provided futures.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: objects to wait on</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: whatever `futures` were provided</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>