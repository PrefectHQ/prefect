---
sidebarDepth: 2
editLink: false
---
# Run Configuration
---
 ## RunConfig
 <div class='class-sig' id='prefect-run-configs-base-runconfig'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.base.RunConfig</p>(labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/base.py#L6">[source]</a></span></div>

Base class for RunConfigs.

A "run config" is an object for configuring a flow run, which maps to a specific agent backend.

**Args**:     <ul class="args"><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-run-configs-base-runconfig-serialize'><p class="prefect-class">prefect.run_configs.base.RunConfig.serialize</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/base.py#L22">[source]</a></span></div>
<p class="methods">Returns a serialized version of the RunConfig.<br><br>**Returns**:     <ul class="args"><li class="args">`dict`: the serialized RunConfig</li></ul></p>|

---
<br>

 ## UniversalRun
 <div class='class-sig' id='prefect-run-configs-base-universalrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.base.UniversalRun</p>(labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/base.py#L33">[source]</a></span></div>

Configure a flow-run to run universally on any Agent.

Unlike the other agent-specific `RunConfig` classes (e.g. `LocalRun` for the Local Agent), the `UniversalRun` run config is compatible with any agent. This can be useful for flows that don't require any custom configuration other than flow labels, allowing for transitioning a flow between agent types without any config changes.

**Args**:     <ul class="args"><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul> **Examples**:

Use the defaults set on the agent:


```python
flow.run_config = UniversalRun()

```

Configure additional labels:


```python
flow.run_config = UniversalRun(labels=["label-1", "label-2"])

```


---
<br>

 ## LocalRun
 <div class='class-sig' id='prefect-run-configs-local-localrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.local.LocalRun</p>(env=None, working_dir=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/local.py#L7">[source]</a></span></div>

Configure a flow-run to run as a Local Process.

**Args**:     <ul class="args"><li class="args">`env (dict, optional)`: Additional environment variables to set for the process     </li><li class="args">`working_dir (str, optional)`: Working directory in which to start the         process, must already exist. If not provided, will be run in the         same directory as the agent.     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul> **Examples**:

Use the defaults set on the agent:


```python
flow.run_config = LocalRun()

```

Run in a specified working directory:


```python
flow.run_config = LocalRun(working_dir="/path/to/working-directory")

```

Set an environment variable in the flow run process:


```python
flow.run_config = LocalRun(env={"SOME_VAR": "value"})

```


---
<br>

 ## DockerRun
 <div class='class-sig' id='prefect-run-configs-docker-dockerrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.docker.DockerRun</p>(image=None, env=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/docker.py#L6">[source]</a></span></div>

Configure a flow-run to run as a Docker container.

**Args**:     <ul class="args"><li class="args">`image (str, optional)`: The image to use     </li><li class="args">`env (dict, optional)`: Additional environment variables to set in the         container     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul> **Examples**:

Use the defaults set on the agent:


```python
flow.run_config = DockerRun()

```

Set an environment variable in the flow run process:


```python
flow.run_config = DockerRun(env={"SOME_VAR": "value"})

```


---
<br>

 ## KubernetesRun
 <div class='class-sig' id='prefect-run-configs-kubernetes-kubernetesrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.kubernetes.KubernetesRun</p>(job_template_path=None, job_template=None, image=None, env=None, cpu_limit=None, cpu_request=None, memory_limit=None, memory_request=None, service_account_name=None, image_pull_secrets=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/kubernetes.py#L8">[source]</a></span></div>

Configure a flow-run to run as a Kubernetes Job.

Kubernetes jobs are configured by filling in a job template at runtime. A job template can be specified either as a path (to be read in at runtime) or an in-memory object (which will be stored along with the flow in Prefect Cloud/Server). By default the job template configured on the Agent is used.

**Args**:     <ul class="args"><li class="args">`job_template_path (str, optional)`: Path to a job template to use. If         a local path (no file scheme, or a `file`/`local` scheme), the job         template will be loaded on initialization and stored on the         `KubernetesRun` object as the `job_template` field.  Otherwise the         job template will be loaded at runtime on the agent.  Supported         runtime file schemes include (`s3`, `gcs`, and `agent` (for paths         local to the runtime agent)).     </li><li class="args">`job_template (str or dict, optional)`: An in-memory job template to         use. Can be either a dict, or a YAML string.     </li><li class="args">`image (str, optional)`: The image to use     </li><li class="args">`env (dict, optional)`: Additional environment variables to set on the job     </li><li class="args">`cpu_limit (float or str, optional)`: The CPU limit to use for the job     </li><li class="args">`cpu_request (float or str, optional)`: The CPU request to use for the job     </li><li class="args">`memory_limit (str, optional)`: The memory limit to use for the job     </li><li class="args">`memory_request (str, optional)`: The memory request to use for the job     </li><li class="args">`service_account_name (str, optional)`: A service account name to use         for this job. If present, overrides any service account configured         on the agent or in the job template.     </li><li class="args">`image_pull_secrets (list, optional)`: A list of image pull secrets to         use for this job. If present, overrides any image pull secrets         configured on the agent or in the job template.     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul> **Examples**:

Use the defaults set on the agent:


```python
flow.run_config = KubernetesRun()

```

Use a local job template, which is stored along with the Flow in Prefect Cloud/Server:


```python
flow.run_config = KubernetesRun(
    job_template_path="my_custom_template.yaml"
)

```

Use a job template stored in S3, but override the image and CPU limit:


```python
flow.run_config = KubernetesRun(
    job_template_path="s3://example-bucket/my_custom_template.yaml",
    image="example/my-custom-image:latest",
    cpu_limit=2,
)

```


---
<br>

 ## ECSRun
 <div class='class-sig' id='prefect-run-configs-ecs-ecsrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.ecs.ECSRun</p>(task_definition=None, task_definition_path=None, task_definition_arn=None, image=None, env=None, cpu=None, memory=None, task_role_arn=None, run_task_kwargs=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/ecs.py#L9">[source]</a></span></div>

Configure a flow-run to run as an ECS Task.

ECS Tasks are composed of task definitions and runtime parameters.

Task definitions can be configured using either the `task_definition`, `task_definition_path`, or `task_definition_arn` parameters. If neither is specified, the default configured on the agent will be used. At runtime this task definition will be registered once per flow version - subsequent runs of the same flow version will reuse the existing definition.

Runtime parameters can be specified via `run_task_kwargs`. These will be merged with any runtime parameters configured on the agent when starting the task.

**Args**:     <ul class="args"><li class="args">`task_definition (dict, optional)`: An in-memory task definition spec         to use. See the [ECS.Client.register_task_definition][3] docs for         more information on task definitions. Note that this definition         will be stored directly in Prefect Cloud/Server - use         `task_definition_path` instead if you wish to avoid this.     </li><li class="args">`task_definition_path (str, optional)`: Path to a task definition spec         to use. If a local path (no file scheme, or a `file`/`local`         scheme), the task definition will be loaded on initialization and         stored on the `ECSRun` object as the `task_definition` field.         Otherwise the task definition will be loaded at runtime on the         agent.  Supported runtime file schemes include (`s3`, `gcs`, and         `agent` (for paths local to the runtime agent)).     </li><li class="args">`task_definition_arn (str, optional)`: A pre-registered task definition         ARN to use (either `family`, `family:version`, or a full task         definition ARN).     </li><li class="args">`image (str, optional)`: The image to use for this task. If not         provided, will be either inferred from the flow's storage (if using         `Docker` storage), or use the default configured on the agent.     </li><li class="args">`env (dict, optional)`: Additional environment variables to set on the task.     </li><li class="args">`cpu (int or str, optional)`: The amount of CPU available to the task. Can         be ether an integer in CPU units (e.g. `1024`), or a string using         vCPUs (e.g. `"1 vcpu"`). Note that ECS imposes strict limits on         what values this can take, see the [ECS documentation][2] for more         information.     </li><li class="args">`memory (int or str, optional)`: The amount of memory available to the         task. Can be ether an integer in MiB (e.g. `1024`), or a string         with units (e.g. `"1 GB"`). Note that ECS imposes strict limits on         what values this can take, see the [ECS documentation][2] for more         information.     </li><li class="args">`task_role_arn (str, optional)`: The name or full ARN for the IAM role         to use for this task. If not provided, the default on the agent         will be used (if configured).     </li><li class="args">`run_task_kwargs (dict, optional)`: Additional keyword arguments to         pass to `run_task` when starting this task. See the         [ECS.Client.run_task][3] docs for more information.     </li><li class="args">`labels (Iterable[str], optional)`: An iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul> **Examples**:

Use the defaults set on the agent:


```python
flow.run_config = ECSRun()

```

Use the default task definition, but override the image and CPU:


```python
flow.run_config = ECSRun(
    image="example/my-custom-image:latest",
    cpu="2 vcpu",
)

```

Use an explicit task definition stored in s3, but override the image and CPU:


```python
flow.run_config = ECSRun(
    task_definition="s3://bucket/path/to/task.yaml",
    image="example/my-custom-image:latest",
    cpu="2 vcpu",
)

```

[1]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition

[2]: https://docs.aws.amazon.com/AmazonECS/latest/userguide/task-cpu-memory-error.html

[3]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>