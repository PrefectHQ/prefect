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
- `map(fn, *args, upstream_states, **kwargs)`: submit function to be mapped
    over based on the edge information contained in `upstream_states`.  Any "mapped" Edge
    will be converted into multiple function submissions, one for each value of the upstream mapped tasks.

Currently, the available executor options are:

- `LocalExecutor`: the no frills, straightforward executor - great for simple
    debugging; tasks are executed immediately upon being called by `executor.submit()`.
- `SynchronousExecutor`: an executor that runs on `dask` primitives with the
    synchronous dask scheduler; currently the default executor
- `DaskExecutor`: the most feature-rich of the executors, this executor runs
    on `dask.distributed` and has support for multiprocessing, multithreading, and distributed execution.

Which executor you choose depends on whether you intend to use things like parallelism
of task execution.
 ## Executor
 <div class='class-sig' id='prefect-engine-executors-base-executor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.base.Executor</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L10">[source]</a></span></div>

Base Executor class that all other executors inherit from.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-map'><p class="prefect-class">prefect.engine.executors.base.Executor.map</p>(fn, *args)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L33">[source]</a></span></div>
<p class="methods">Submit a function to be mapped over its iterable arguments.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments that the function will be mapped over</li></ul>**Returns**:     <ul class="args"><li class="args">`List[Any]`: the result of computating the function over the arguments</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-queue'><p class="prefect-class">prefect.engine.executors.base.Executor.queue</p>(maxsize=0)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L73">[source]</a></span></div>
<p class="methods">Creates an executor-compatible Queue object that can share state across tasks.<br><br>**Args**:     <ul class="args"><li class="args">`maxsize (int)`: maxsize of the queue; defaults to 0 (infinite)</li></ul>**Returns**:     <ul class="args"><li class="args">`Queue`: an executor compatible queue that can be shared among tasks</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-start'><p class="prefect-class">prefect.engine.executors.base.Executor.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L23">[source]</a></span></div>
<p class="methods">Context manager for initializing execution.<br><br>Any initialization this executor needs to perform should be done in this context manager, and torn down after yielding.</p>|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-submit'><p class="prefect-class">prefect.engine.executors.base.Executor.submit</p>(fn, *args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L47">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns a future-like object.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: a future-like object</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-base-executor-wait'><p class="prefect-class">prefect.engine.executors.base.Executor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py#L61">[source]</a></span></div>
<p class="methods">Resolves futures to their values. Blocks until the future is complete.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: iterable of futures to compute</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: an iterable of resolved futures</li></ul></p>|

---
<br>

 ## DaskExecutor
 <div class='class-sig' id='prefect-engine-executors-dask-daskexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor</p>(address=None, local_processes=None, debug=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L15">[source]</a></span></div>

An executor that runs all functions using the `dask.distributed` scheduler on a (possibly local) dask cluster.  If you already have one running, simply provide the address of the scheduler upon initialization; otherwise, one will be created (and subsequently torn down) within the `start()` contextmanager.

Note that if you have tasks with tags of the form `"dask-resource:KEY=NUM"` they will be parsed and passed as [Worker Resources](https://distributed.dask.org/en/latest/resources.html) of the form `{"KEY": float(NUM)}` to the Dask Scheduler.

**Args**:     <ul class="args"><li class="args">`address (string, optional)`: address of a currently running dask         scheduler; if one is not provided, a `distributed.LocalCluster()` will be created in `executor.start()`.         Defaults to `None`     </li><li class="args">`local_processes (bool, optional)`: whether to use multiprocessing or not         (computations will still be multithreaded). Ignored if address is provided.         Defaults to `False`.     </li><li class="args">`debug (bool, optional)`: whether to operate in debug mode; `debug=True`         will produce many additional dask logs. Defaults to the `debug` value in your Prefect configuration     </li><li class="args">`**kwargs (dict, optional)`: additional kwargs to be passed to the         `dask.distributed.Client` upon initialization (e.g., `n_workers`)</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-map'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.map</p>(fn, *args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L155">[source]</a></span></div>
<p class="methods">Submit a function to be mapped over its iterable arguments.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments that the function will be mapped over     </li><li class="args">`**kwargs (Any)`: additional keyword arguments that will be passed to the Dask Client</li></ul>**Returns**:     <ul class="args"><li class="args">`List[Future]`: a list of Future-like objects that represent each computation of         fn(*a), where a = zip(*args)[i]</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-queue'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.queue</p>(maxsize=0, client=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L105">[source]</a></span></div>
<p class="methods">Creates an executor-compatible Queue object that can share state across tasks.<br><br>**Args**:     <ul class="args"><li class="args">`maxsize (int, optional)`: `maxsize` for the Queue; defaults to 0         (interpreted as no size limitation)     </li><li class="args">`client (dask.distributed.Client, optional)`: which client to         associate the Queue with; defaults to `self.client`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-start'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L61">[source]</a></span></div>
<p class="methods">Context manager for initializing execution.<br><br>Creates a `dask.distributed.Client` and yields it.</p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-submit'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.submit</p>(fn, *args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L128">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns a Future object.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul>**Returns**:     <ul class="args"><li class="args">`Future`: a Future-like object that represents the computation of `fn(*args, **kwargs)`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-dask-daskexecutor-wait'><p class="prefect-class">prefect.engine.executors.dask.DaskExecutor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/dask.py#L187">[source]</a></span></div>
<p class="methods">Resolves the Future objects to their values. Blocks until the computation is complete.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: single or iterable of future-like objects to compute</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: an iterable of resolved futures with similar shape to the input</li></ul></p>|

---
<br>

 ## LocalExecutor
 <div class='class-sig' id='prefect-engine-executors-local-localexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.local.LocalExecutor</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/local.py#L7">[source]</a></span></div>

An executor that runs all functions synchronously and immediately in the main thread.  To be used mainly for debugging purposes.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-local-localexecutor-map'><p class="prefect-class">prefect.engine.executors.local.LocalExecutor.map</p>(fn, *args)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/local.py#L27">[source]</a></span></div>
<p class="methods">Submit a function to be mapped over its iterable arguments.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments that the function will be mapped over</li></ul>**Returns**:     <ul class="args"><li class="args">`List[Any]`: the result of computating the function over the arguments</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-local-localexecutor-submit'><p class="prefect-class">prefect.engine.executors.local.LocalExecutor.submit</p>(fn, *args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/local.py#L13">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns the result of the computation.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the result of `fn(*args, **kwargs)`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-local-localexecutor-wait'><p class="prefect-class">prefect.engine.executors.local.LocalExecutor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/local.py#L44">[source]</a></span></div>
<p class="methods">Returns the results of the provided futures.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: objects to wait on</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: whatever `futures` were provided</li></ul></p>|

---
<br>

 ## SynchronousExecutor
 <div class='class-sig' id='prefect-engine-executors-sync-synchronousexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.executors.sync.SynchronousExecutor</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/sync.py#L13">[source]</a></span></div>

An executor that runs all functions synchronously using `dask`.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-executors-sync-synchronousexecutor-map'><p class="prefect-class">prefect.engine.executors.sync.SynchronousExecutor.map</p>(fn, *args)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/sync.py#L46">[source]</a></span></div>
<p class="methods">Submit a function to be mapped over its iterable arguments.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments that the function will be mapped over</li></ul>**Returns**:     <ul class="args"><li class="args">`List[dask.delayed]`: the result of computating the function over the arguments</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-sync-synchronousexecutor-queue'><p class="prefect-class">prefect.engine.executors.sync.SynchronousExecutor.queue</p>(maxsize=0)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/sync.py#L28">[source]</a></span></div>
<p class="methods">Creates an executor-compatible Queue object that can share state across tasks.<br><br>**Args**:     <ul class="args"><li class="args">`maxsize (int)`: maxsize of the queue; defaults to 0 (infinite)</li></ul>**Returns**:     <ul class="args"><li class="args">`Queue`: an executor compatible queue that can be shared among tasks</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-sync-synchronousexecutor-start'><p class="prefect-class">prefect.engine.executors.sync.SynchronousExecutor.start</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/sync.py#L18">[source]</a></span></div>
<p class="methods">Context manager for initializing execution.<br><br>Configures `dask` and yields the `dask.config` contextmanager.</p>|
 | <div class='method-sig' id='prefect-engine-executors-sync-synchronousexecutor-submit'><p class="prefect-class">prefect.engine.executors.sync.SynchronousExecutor.submit</p>(fn, *args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/sync.py#L32">[source]</a></span></div>
<p class="methods">Submit a function to the executor for execution. Returns a `dask.delayed` object.<br><br>**Args**:     <ul class="args"><li class="args">`fn (Callable)`: function that is being submitted for execution     </li><li class="args">`*args (Any)`: arguments to be passed to `fn`     </li><li class="args">`**kwargs (Any)`: keyword arguments to be passed to `fn`</li></ul>**Returns**:     <ul class="args"><li class="args">`dask.delayed`: a `dask.delayed` object that represents the computation of `fn(*args, **kwargs)`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-executors-sync-synchronousexecutor-wait'><p class="prefect-class">prefect.engine.executors.sync.SynchronousExecutor.wait</p>(futures)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/sync.py#L63">[source]</a></span></div>
<p class="methods">Resolves a `dask.delayed` object to its values. Blocks until the computation is complete.<br><br>**Args**:     <ul class="args"><li class="args">`futures (Any)`: iterable of `dask.delayed` objects to compute</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: an iterable of resolved futures</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 16, 2019 at 04:54 UTC</p>