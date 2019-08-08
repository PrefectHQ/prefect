---
sidebarDepth: 2
editLink: false
---
# Execution Environments
---
Execution environments encapsulate the logic for where your Flow should execute in Prefect Cloud.

Currently, we recommend all users deploy their Flow using the `RemoteEnvironment` configured with the
appropriate choice of executor.
 ## LocalEnvironment
 <div class='class-sig' id='prefect-environments-execution-local-localenvironment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.execution.local.LocalEnvironment</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/local.py#L9">[source]</a></span></div>

A LocalEnvironment class for executing a flow contained in Storage in the local process. Execution will first attempt to call `get_flow` on the storage object, and if that fails it will fall back to `get_env_runner`.  If `get_env_runner` is used, the environment variables from this process will be passed.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-execution-local-localenvironment-execute'><p class="prefect-class">prefect.environments.execution.local.LocalEnvironment.execute</p>(storage, flow_location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/local.py#L20">[source]</a></span></div>
<p class="methods">Executes the flow for this environment from the storage parameter, by calling `get_flow` on the storage; if that fails, `get_env_runner` will be used with the OS environment variables inherited from this process.<br><br>**Args**:     <ul class="args"><li class="args">`storage (Storage)`: the Storage object that contains the flow     </li><li class="args">`flow_location (str)`: the location of the Flow to execute     </li><li class="args">`**kwargs (Any)`: additional keyword arguments to pass to the runner</li></ul></p>|

---
<br>

 ## RemoteEnvironment
 <div class='class-sig' id='prefect-environments-execution-remote-remoteenvironment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.execution.remote.RemoteEnvironment</p>(executor=None, executor_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/remote.py#L12">[source]</a></span></div>

RemoteEnvironment is an environment which takes in information about an executor and runs the flow in place using that executor.

**Example**: 
```python
# using a RemoteEnvironment w/ an existing Dask cluster

env = RemoteEnvironment(
    executor="prefect.engine.executors.DaskExecutor",
    executor_kwargs={"address": "tcp://dask_scheduler_address"}
)

f = Flow("dummy flow", environment=env)

```

**Args**:     <ul class="args"><li class="args">`executor (str, optional)`: an importable string to an executor class; defaults         to `prefect.config.engine.executor.default_class`     </li><li class="args">`executor_kwargs (dict, optional)`: a dictionary of kwargs to be passed to         the executor; defaults to an empty dictionary</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-execution-remote-remoteenvironment-execute'><p class="prefect-class">prefect.environments.execution.remote.RemoteEnvironment.execute</p>(storage, flow_location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/remote.py#L41">[source]</a></span></div>
<p class="methods">Run a flow from the `flow_location` here using the specified executor and executor kwargs.<br><br>**Args**:     <ul class="args"><li class="args">`storage (Storage)`: the storage object that contains information relating         to where and how the flow is stored     </li><li class="args">`flow_location (str)`: the location of the Flow to execute     </li><li class="args">`**kwargs (Any)`: additional keyword arguments to pass to the runner</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 7, 2019 at 16:05 UTC</p>