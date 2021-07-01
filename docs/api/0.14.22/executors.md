---
sidebarDepth: 2
editLink: false
---
# Executors
---
Prefect Executors are responsible for running tasks in a flow. During
execution of a flow run, a flow's executor will be initialized, used to execute
all tasks in the flow, then shutdown.

Currently, the available executor options are:

- `LocalExecutor`: the default, no frills executor. All tasks are executed in
    a single thread, parallelism is not supported.
- `LocalDaskExecutor`: an executor that runs on `dask` primitives with a
    using either threads or processes.
- `DaskExecutor`: the most feature-rich of the executors, this executor runs
    on `dask.distributed` and has support for distributed execution.

Which executor you choose depends on the performance requirements and
characteristics of your Flow.  See [the executors
docs](/orchestration/flow_config/executors.md) for more information.
 ## Executor
 <div class='class-sig' id='prefect-executors-base-executor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.executors.base.Executor</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/executors/base.py#L7">[source]</a></span></div>

Base Executor class that all other executors inherit from.


---
<br>

 ## LocalExecutor
 <div class='class-sig' id='prefect-executors-local-localexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.executors.local.LocalExecutor</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/executors/local.py#L6">[source]</a></span></div>

An executor that runs all functions synchronously and immediately in the main thread.  To be used mainly for debugging purposes.


---
<br>

 ## LocalDaskExecutor
 <div class='class-sig' id='prefect-executors-dask-localdaskexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.executors.dask.LocalDaskExecutor</p>(scheduler=&quot;threads&quot;, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/executors/dask.py#L426">[source]</a></span></div>

An executor that runs all functions locally using `dask` and a configurable dask scheduler.

**Args**:     <ul class="args"><li class="args">`scheduler (str)`: The local dask scheduler to use; common options are         "threads", "processes", and "synchronous".  Defaults to "threads".     </li><li class="args">`**kwargs (Any)`: Additional keyword arguments to pass to dask config</li></ul>


---
<br>

 ## DaskExecutor
 <div class='class-sig' id='prefect-executors-dask-daskexecutor'><p class="prefect-sig">class </p><p class="prefect-class">prefect.executors.dask.DaskExecutor</p>(address=None, cluster_class=None, cluster_kwargs=None, adapt_kwargs=None, client_kwargs=None, debug=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/executors/dask.py#L63">[source]</a></span></div>

An executor that runs all functions using the `dask.distributed` scheduler.

By default a temporary `distributed.LocalCluster` is created (and subsequently torn down) within the `start()` contextmanager. To use a different cluster class (e.g. [`dask_kubernetes.KubeCluster`](https://kubernetes.dask.org/)), you can specify `cluster_class`/`cluster_kwargs`.

Alternatively, if you already have a dask cluster running, you can provide the address of the scheduler via the `address` kwarg.

Note that if you have tasks with tags of the form `"dask-resource:KEY=NUM"` they will be parsed and passed as [Worker Resources](https://distributed.dask.org/en/latest/resources.html) of the form `{"KEY": float(NUM)}` to the Dask Scheduler.

**Args**:     <ul class="args"><li class="args">`address (string, optional)`: address of a currently running dask         scheduler; if one is not provided, a temporary cluster will be         created in `executor.start()`.  Defaults to `None`.     </li><li class="args">`cluster_class (string or callable, optional)`: the cluster class to use         when creating a temporary dask cluster. Can be either the full         class name (e.g. `"distributed.LocalCluster"`), or the class itself.     </li><li class="args">`cluster_kwargs (dict, optional)`: addtional kwargs to pass to the        `cluster_class` when creating a temporary dask cluster.     </li><li class="args">`adapt_kwargs (dict, optional)`: additional kwargs to pass to `cluster.adapt`         when creating a temporary dask cluster. Note that adaptive scaling         is only enabled if `adapt_kwargs` are provided.     </li><li class="args">`client_kwargs (dict, optional)`: additional kwargs to use when creating a         [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client).     </li><li class="args">`debug (bool, optional)`: When running with a local cluster, setting         `debug=True` will increase dask's logging level, providing         potentially useful debug info. Defaults to the `debug` value in         your Prefect configuration.</li></ul> **Examples**:

Using a temporary local dask cluster:


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


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>