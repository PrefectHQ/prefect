---
sidebarDepth: 2
editLink: false
---
# Execution Environments
---
 ## LocalEnvironment
 <div class='class-sig' id='prefect-environments-execution-local-localenvironment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.execution.local.LocalEnvironment</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/local.py#L9">[source]</a></span></div>

A LocalEnvironment class for executing a flow contained in Storage in the local process. Execution will first attempt to call `get_flow` on the storage object, and if that fails it will fall back to `get_env_runner`.  If `get_env_runner` is used, the environment variables from this process will be passed.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-execution-local-localenvironment-execute'><p class="prefect-class">prefect.environments.execution.local.LocalEnvironment.execute</p>(storage, flow_location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/local.py#L20">[source]</a></span></div>
<p class="methods">Executes the flow for this environment from the storage parameter, by calling `get_flow` on the storage; if that fails, `get_env_runner` will be used with the OS environment variables inherited from this process.<br><br>**Args**:     <ul class="args"><li class="args">`storage (Storage)`: the Storage object that contains the flow     </li><li class="args">`flow_location (str)`: the location of the Flow to execute     </li><li class="args">`**kwargs (Any)`: additional keyword arguments to pass to the runner</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.3+275.g38ab4505 on May 28, 2019 at 20:38 UTC</p>