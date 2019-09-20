---
sidebarDepth: 2
editLink: false
---
# Execution Environments
---
Execution environments encapsulate the logic for where your Flow should execute in Prefect Cloud.

Currently, we recommend all users deploy their Flow using the `RemoteEnvironment` configured with the
appropriate choice of executor.
 ## DaskKubernetesEnvironment
 <div class='class-sig' id='prefect-environments-execution-dask-k8s-daskkubernetesenvironment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.execution.dask.k8s.DaskKubernetesEnvironment</p>(min_workers=1, max_workers=2, private_registry=False, docker_secret=None, labels=None, scheduler_spec_file=None, worker_spec_file=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/dask/k8s.py#L16">[source]</a></span></div>

DaskKubernetesEnvironment is an environment which deploys your flow (stored in a Docker image) on Kubernetes by spinning up a temporary Dask Cluster (using [dask-kubernetes](https://kubernetes.dask.org/en/latest/)) and running the Prefect `DaskExecutor` on this cluster.

If pulling from a private docker registry, `setup` will ensure the appropriate kubernetes secret exists; `execute` creates a single job that has the role of spinning up a dask executor and running the flow. The job created in the execute function does have the requirement in that it needs to have an `identifier_label` set with a UUID so resources can be cleaned up independently of other deployments.

It is possible to provide a custom scheduler and worker spec YAML files through the `scheduler_spec_file` and `worker_spec_file` arguments. These specs (if provided) will be used in place of the defaults. Your spec files should be modeled after the job.yaml and worker_pod.yaml found at https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments/execution/dask The main aspects to be aware of are the `command` and `args` on the container. These environment variables are required for cloud do not need to be included because they are instead automatically added and populated during execution: PREFECT__CLOUD__GRAPHQL, PREFECT__CLOUD__AUTH_TOKEN, PREFECT__CONTEXT__FLOW_RUN_ID, PREFECT__CONTEXT__NAMESPACE, PREFECT__CONTEXT__IMAGE, PREFECT__CONTEXT__FLOW_FILE_PATH, PREFECT__CLOUD__USE_LOCAL_SECRETS, PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS, PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS, PREFECT__ENGINE__EXECUTOR__DEFAULT_CLASS, PREFECT__LOGGING__LOG_TO_CLOUD

**Args**:     <ul class="args"><li class="args">`min_workers (int, optional)`: the minimum allowed number of Dask worker pods; defaults to 1     </li><li class="args">`max_workers (int, optional)`: the maximum allowed number of Dask worker pods; defaults to 1     </li><li class="args">`private_registry (bool, optional)`: a boolean specifying whether your Flow's Docker container will be in a private         Docker registry; if so, requires a Prefect Secret containing your docker credentials to be set.         Defaults to `False`.     </li><li class="args">`docker_secret (str, optional)`: the name of the Prefect Secret containing your Docker credentials; defaults to         `"DOCKER_REGISTRY_CREDENTIALS"`.  This Secret should be a dictionary containing the following keys: `"docker-server"`,         `"docker-username"`, `"docker-password"`, and `"docker-email"`.     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string identifiers used by Prefect         Agents when polling for work     </li><li class="args">`scheduler_spec_file (str, optional)`: Path to a scheduler spec YAML file     </li><li class="args">`worker_spec_file (str, optional)`: Path to a worker spec YAML file</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-execution-dask-k8s-daskkubernetesenvironment-create-flow-run-job'><p class="prefect-class">prefect.environments.execution.dask.k8s.DaskKubernetesEnvironment.create_flow_run_job</p>(docker_name, flow_file_path)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/dask/k8s.py#L179">[source]</a></span></div>
<p class="methods">Creates a Kubernetes job to run the flow using the information stored on the Docker storage object.<br><br>**Args**:     <ul class="args"><li class="args">`docker_name (str)`: the full name of the docker image (registry/name:tag)     </li><li class="args">`flow_file_path (str)`: location of the flow file in the image</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-execution-dask-k8s-daskkubernetesenvironment-execute'><p class="prefect-class">prefect.environments.execution.dask.k8s.DaskKubernetesEnvironment.execute</p>(storage, flow_location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/dask/k8s.py#L112">[source]</a></span></div>
<p class="methods">Create a single Kubernetes job that spins up a dask scheduler, dynamically creates worker pods, and runs the flow.<br><br>**Args**:     <ul class="args"><li class="args">`storage (Docker)`: the Docker storage object that contains information relating         to the image which houses the flow     </li><li class="args">`flow_location (str)`: the location of the Flow to execute     </li><li class="args">`**kwargs (Any)`: additional keyword arguments to pass to the runner</li></ul>**Raises**:     <ul class="args"><li class="args">`TypeError`: if the storage is not `Docker`</li></ul></p>|
 | <div class='method-sig' id='prefect-environments-execution-dask-k8s-daskkubernetesenvironment-run-flow'><p class="prefect-class">prefect.environments.execution.dask.k8s.DaskKubernetesEnvironment.run_flow</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/dask/k8s.py#L220">[source]</a></span></div>
<p class="methods">Run the flow from specified flow_file_path location using a Dask executor</p>|
 | <div class='method-sig' id='prefect-environments-execution-dask-k8s-daskkubernetesenvironment-setup'><p class="prefect-class">prefect.environments.execution.dask.k8s.DaskKubernetesEnvironment.setup</p>(storage)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/dask/k8s.py#L81">[source]</a></span></div>
<p class="methods">Sets up any infrastructure needed for this environment<br><br>**Args**:     <ul class="args"><li class="args">`storage (Storage)`: the Storage object that contains the flow</li></ul></p>|

---
<br>

 ## LocalEnvironment
 <div class='class-sig' id='prefect-environments-execution-local-localenvironment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.execution.local.LocalEnvironment</p>(labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/local.py#L9">[source]</a></span></div>

A LocalEnvironment class for executing a flow contained in Storage in the local process. Execution will first attempt to call `get_flow` on the storage object, and if that fails it will fall back to `get_env_runner`.  If `get_env_runner` is used, the environment variables from this process will be passed.

**Args**:     <ul class="args"><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string identifiers used by Prefect         Agents when polling for work</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-execution-local-localenvironment-execute'><p class="prefect-class">prefect.environments.execution.local.LocalEnvironment.execute</p>(storage, flow_location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/local.py#L24">[source]</a></span></div>
<p class="methods">Executes the flow for this environment from the storage parameter, by calling `get_flow` on the storage; if that fails, `get_env_runner` will be used with the OS environment variables inherited from this process.<br><br>**Args**:     <ul class="args"><li class="args">`storage (Storage)`: the Storage object that contains the flow     </li><li class="args">`flow_location (str)`: the location of the Flow to execute     </li><li class="args">`**kwargs (Any)`: additional keyword arguments to pass to the runner</li></ul></p>|

---
<br>

 ## RemoteEnvironment
 <div class='class-sig' id='prefect-environments-execution-remote-remoteenvironment'><p class="prefect-sig">class </p><p class="prefect-class">prefect.environments.execution.remote.RemoteEnvironment</p>(executor=None, executor_kwargs=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/remote.py#L12">[source]</a></span></div>

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

**Args**:     <ul class="args"><li class="args">`executor (str, optional)`: an importable string to an executor class; defaults         to `prefect.config.engine.executor.default_class`     </li><li class="args">`executor_kwargs (dict, optional)`: a dictionary of kwargs to be passed to         the executor; defaults to an empty dictionary     </li><li class="args">`labels (List[str], optional)`: a list of labels, which are arbitrary string identifiers used by Prefect         Agents when polling for work</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-environments-execution-remote-remoteenvironment-execute'><p class="prefect-class">prefect.environments.execution.remote.RemoteEnvironment.execute</p>(storage, flow_location, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/environments/execution/remote.py#L48">[source]</a></span></div>
<p class="methods">Run a flow from the `flow_location` here using the specified executor and executor kwargs.<br><br>**Args**:     <ul class="args"><li class="args">`storage (Storage)`: the storage object that contains information relating         to where and how the flow is stored     </li><li class="args">`flow_location (str)`: the location of the Flow to execute     </li><li class="args">`**kwargs (Any)`: additional keyword arguments to pass to the runner</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on September 20, 2019 at 19:42 UTC</p>