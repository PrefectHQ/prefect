---
sidebarDepth: 2
editLink: false
---
# Run Configuration
---
 ## RunConfig
 <div class='class-sig' id='prefect-run-configs-base-runconfig'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.base.RunConfig</p>(env=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/base.py#L6">[source]</a></span></div>

Base class for RunConfigs.

A "run config" is an object for configuring a flow run, which maps to a specific agent backend.

**Args**:     <ul class="args"><li class="args">`env (dict, optional)`: Additional environment variables to set     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-run-configs-base-runconfig-serialize'><p class="prefect-class">prefect.run_configs.base.RunConfig.serialize</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/base.py#L24">[source]</a></span></div>
<p class="methods">Returns a serialized version of the RunConfig.<br><br>**Returns**:     <ul class="args"><li class="args">`dict`: the serialized RunConfig</li></ul></p>|

---
<br>

 ## UniversalRun
 <div class='class-sig' id='prefect-run-configs-base-universalrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.base.UniversalRun</p>(env=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/base.py#L41">[source]</a></span></div>

Configure a flow-run to run universally on any Agent.

Unlike the other agent-specific `RunConfig` classes (e.g. `LocalRun` for the Local Agent), the `UniversalRun` run config is compatible with any agent. This can be useful for flows that don't require any custom configuration other than flow labels, allowing for transitioning a flow between agent types without any config changes.

**Args**:     <ul class="args"><li class="args">`env (dict, optional)`: Additional environment variables to set     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul> **Examples**:

Use the defaults set on the agent:


```python
flow.run_config = UniversalRun()

```

Configure additional labels:


```python
flow.run_config = UniversalRun(env={"SOME_VAR": "value"}, labels=["label-1", "label-2"])

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
 <div class='class-sig' id='prefect-run-configs-docker-dockerrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.docker.DockerRun</p>(image=None, env=None, labels=None, ports=None, host_config=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/docker.py#L6">[source]</a></span></div>

Configure a flow-run to run as a Docker container.

**Args**:     <ul class="args"><li class="args">`image (str, optional)`: The image to use     </li><li class="args">`env (dict, optional)`: Additional environment variables to set in the         container     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work     </li><li class="args">`ports (Iterable[int], optional)`: an iterable of ports to pass to the         Docker Agent which are used to expose container ports.     </li><li class="args">`host_config (dict, optional)`: A dictionary or runtime arguments to pass to         the Docker Agent. See link below for options.         https://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_host_config</li></ul> **Examples**:

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
 <div class='class-sig' id='prefect-run-configs-kubernetes-kubernetesrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.kubernetes.KubernetesRun</p>(job_template_path=None, job_template=None, image=None, env=None, cpu_limit=None, cpu_request=None, memory_limit=None, memory_request=None, service_account_name=None, image_pull_secrets=None, labels=None, image_pull_policy=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/kubernetes.py#L9">[source]</a></span></div>

Configure a flow-run to run as a Kubernetes Job.

Kubernetes jobs are configured by filling in a job template at runtime. A job template can be specified either as a path (to be read in at runtime) or an in-memory object (which will be stored along with the flow in Prefect Cloud/Server). By default the job template configured on the Agent is used.

**Args**:     <ul class="args"><li class="args">`job_template_path (str, optional)`: Path to a job template to use. If         a local path (no file scheme, or a `file`/`local` scheme), the job         template will be loaded on initialization and stored on the         `KubernetesRun` object as the `job_template` field.  Otherwise the         job template will be loaded at runtime on the agent.  Supported         runtime file schemes include (`s3`, `gcs`, and `agent` (for paths         local to the runtime agent)).     </li><li class="args">`job_template (str or dict, optional)`: An in-memory job template to         use. Can be either a dict, or a YAML string.     </li><li class="args">`image (str, optional)`: The image to use     </li><li class="args">`env (dict, optional)`: Additional environment variables to set on the job     </li><li class="args">`cpu_limit (float or str, optional)`: The CPU limit to use for the job     </li><li class="args">`cpu_request (float or str, optional)`: The CPU request to use for the job     </li><li class="args">`memory_limit (str, optional)`: The memory limit to use for the job     </li><li class="args">`memory_request (str, optional)`: The memory request to use for the job     </li><li class="args">`service_account_name (str, optional)`: A service account name to use         for this job. If present, overrides any service account configured         on the agent or in the job template.     </li><li class="args">`image_pull_secrets (list, optional)`: A list of image pull secrets to         use for this job. If present, overrides any image pull secrets         configured on the agent or in the job template.     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work     </li><li class="args">`image_pull_policy (str, optional)`: The imagePullPolicy to use for the job.         https://kubernetes.io/docs/concepts/configuration/overview/#container-images</li></ul> **Examples**:

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

Use an image not tagged with :latest, and set the image pull policy to `Always`:


```python
flow.run_config = KubernetesRun(
    image="example/my-custom-image:my-tag,
    image_pull_policy="Always"
)

```

Augment the `job_template` with a custom label (use the default [job template](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/job_template.yaml) as a base to build on. Once a `job_template` is specified, the default is no longer used):


```python
flow.run_config = KubernetesRun(
    image="example/my-custom-image:my-tag,
    job_template={
        {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "spec": {
                "template": {
                    "metadata": {
                        "labels": {
                            "my-custom-label": "something"
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "flow"
                            }
                        ]
                    }
                }
            }
        }
    }
)

```


---
<br>

 ## ECSRun
 <div class='class-sig' id='prefect-run-configs-ecs-ecsrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.ecs.ECSRun</p>(task_definition=None, task_definition_path=None, task_definition_arn=None, image=None, env=None, cpu=None, memory=None, task_role_arn=None, execution_role_arn=None, run_task_kwargs=None, labels=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/ecs.py#L9">[source]</a></span></div>

Configure a flow-run to run as an ECS Task.

ECS Tasks are composed of task definitions and runtime parameters.

Task definitions can be configured using either the `task_definition`, `task_definition_path`, or `task_definition_arn` parameters. If neither is specified, the default configured on the agent will be used. At runtime this task definition will be registered once per flow version - subsequent runs of the same flow version will reuse the existing definition.

Runtime parameters can be specified via `run_task_kwargs`. These will be merged with any runtime parameters configured on the agent when starting the task.

Note that certain Prefect specific environment variables defined within the `task_definition` will be overwritten by the ECS Agent when a new task is run (see method get_run_task_kwargs of the ECSAgent). For example, although the variable `PREFECT__LOGGING__LEVEL` might be defined within `containerDefinitions` (of the `task_definition`), it will first be ovewritten with the Prefect config and then by `env` (if defined). Therefore, do not set any Prefect specific environment variables within `task_definition`, `task_definition_path` or `task_definition_arn`. Instead, use the top-level `ECSRun.env` setting.

**Args**:     <ul class="args"><li class="args">`task_definition (dict, optional)`: An in-memory task definition spec         to use. The flow will be executed in a container named `flow` - if         a container named `flow` isn't part of the task definition, Prefect         will add a new container with that name.  See the         [ECS.Client.register_task_definition][1] docs for more information         on task definitions. Note that this definition will be stored         directly in Prefect Cloud/Server - use `task_definition_path`         instead if you wish to avoid this.     </li><li class="args">`task_definition_path (str, optional)`: Path to a task definition spec         to use. If you started your agent in a local process (with         `prefect agent ecs start --label your-label`), then you can reference a path         on that machine (use either no file scheme, or a `file`/`local` scheme).         The task definition will then be loaded on initialization         and stored on the `ECSRun` object as the `task_definition` field.         Otherwise the task definition will be loaded at runtime on the         agent.  Supported runtime file schemes include `s3`, `gcs`, and         `agent` (for paths local to the runtime agent).     </li><li class="args">`task_definition_arn (str, optional)`: A pre-registered task definition         ARN to use (either `family:revision`, or a full task         definition ARN). This task definition must include a container         named `flow` (which will be used to run the flow).     </li><li class="args">`image (str, optional)`: The image to use for this task. If not         provided, will be either inferred from the flow's storage (if using         `Docker` storage), or use the default configured on the agent. Note that         when using an ECR image, you need to explicitly provide the         `execution_role_arn`, unless you set this role explicitly in a custom `task_definition`.         This means: either you provide a custom `task_definition` that contains         both the image and `execution_role_arn` (with ECR permissions),         or you provide both a custom `image` and an `execution_role_arn`         simultaneously.     </li><li class="args">`env (dict, optional)`: Additional environment variables to set on the task.     </li><li class="args">`cpu (int or str, optional)`: The amount of CPU available to the task. Can         be ether an integer in CPU units (e.g. `1024`), or a string using         vCPUs (e.g. `"1 vcpu"`). Note that ECS imposes strict limits on         what values this can take, see the [ECS documentation][2] for more         information.     </li><li class="args">`memory (int or str, optional)`: The amount of memory available to the         task. Can be ether an integer in MiB (e.g. `1024`), or a string         with units (e.g. `"1 GB"`). Note that ECS imposes strict limits on         what values this can take, see the [ECS documentation][2] for more         information.     </li><li class="args">`task_role_arn (str, optional)`: The full ARN of the IAM role         to use for this task. If you provide a custom `task_definition` that         already contains the `task_role_arn`, then you can skip this argument.         You can also skip it when your flow doesn't need access to any AWS         resources such as S3. But if you use S3 storage (or results) and you don't set         a custom `task_definition`, this role must be set explicitly.     </li><li class="args">`execution_role_arn (str, optional)`: The execution role ARN to use         when registering a task definition for this task. If you provide a custom         `task_definition` that already contains the `execution_role_arn`, then you         can skip this argument. But if you don't set any custom `task_definition`,         and you supply an ECR `image`, then you need to set an `execution_role_arn`         explicitly to grant ECR access.     </li><li class="args">`run_task_kwargs (dict, optional)`: Additional keyword arguments to         pass to `run_task` when starting this task. It should be used only for         runtime-specific arguments such as `cpu`, `memory`, `cluster`, or `launchType`,         rather than `task_definition`-specific arguments.         See the [ECS.Client.run_task][3] docs for more information.     </li><li class="args">`labels (Iterable[str], optional)`: An iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work</li></ul> **Examples**:

1) Use the defaults set on the agent (assuming label "prod"):


```python
flow.run_config = ECSRun(labels=["prod"])

```

2) Use a custom task definition uploaded to S3 as a YAML file. This task definition contains a container named "flow", as well as a custom execution role and task role. The flow should be picked up for execution by an agent with label "prod" and should be deployed to a cluster called "prefectEcsCluster".


```python
flow.run_config = ECSRun(
    labels=["prod"],
    task_definition_path="s3://bucket/flow_task_definition.yaml",
    run_task_kwargs=dict(cluster="prefectEcsCluster"),
)

```

An example of `flow_task_definition.yaml`: 
```yaml
family: prefectFlow
requiresCompatibilities:
    - FARGATE
networkMode: awsvpc
cpu: 1024
memory: 2048
taskRoleArn: arn:aws:iam::XXX:role/prefectTaskRole
executionRoleArn: arn:aws:iam::XXX:role/prefectECSAgentTaskExecutionRole
containerDefinitions:
- name: flow
    image: "XXX.dkr.ecr.us-east-1.amazonaws.com/image_name:latest"
    essential: true
    environment:
    - name: AWS_RETRY_MODE
        value: "adaptive"
    - name: AWS_MAX_ATTEMPTS
        value: "10"
    logConfiguration:
    logDriver: awslogs
    options:
        awslogs-group: "/ecs/prefectEcsAgent"
        awslogs-region: "us-east-1"
        awslogs-stream-prefix: "ecs"
        awslogs-create-group: "true"

```

3) Use a custom pre-registered task definition (referenced by `family:revision` or by a full ARN), then deploy the flow to a cluster called "prefectEcsCluster":


```python
flow.run_config = ECSRun(
    labels=["prod"],
    task_definition_arn="prefectFlow:1",
    # or using a full ARN:
    # task_definition_arn="arn:aws:ecs:us-east-1:XXX:task-definition/prefectFlow:1"
    run_task_kwargs=dict(cluster="prefectEcsCluster"),
)

```

4) Let Prefect register a new task definition for a flow with S3 storage and a custom ECR image:


```python
flow.run_config = ECSRun(
    labels=["prod"],
    task_role_arn="arn:aws:iam::XXXX:role/prefectTaskRole",
    execution_role_arn="arn:aws:iam::XXXX:role/prefectECSAgentTaskExecutionRole",
    image="XXXX.dkr.ecr.us-east-1.amazonaws.com/image_name:latest",
    run_task_kwargs=dict(cluster="prefectEcsCluster"),
)

```

5) Use the default task definition, but override the image and CPU:


```python
flow.run_config = ECSRun(
    execution_role_arn="arn:aws:iam::XXXX:role/prefectECSAgentTaskExecutionRole",
    image="XXXX.dkr.ecr.us-east-1.amazonaws.com/image_name:latest",
    cpu="2 vcpu",
)

```

6) Use an explicit task definition stored in S3 as a YAML file, but override the image and CPU:


```python
flow.run_config = ECSRun(
    task_definition="s3://bucket/flow_task_definition.yaml",
    image="XXXX.dkr.ecr.us-east-1.amazonaws.com/image_name:latest",
    cpu="2 vcpu",
)

```

7) An example flow showing ECSRun with a `task_definition` defined as dictionary, and S3 storage: 
```python
import prefect
from prefect.storage import S3
from prefect.run_configs import ECSRun
from prefect import task, Flow
from prefect.client.secrets import Secret


FLOW_NAME = "ecs_demo_ecr"
ACCOUNT_ID = Secret("AWS_ACCOUNT_ID").get()
STORAGE = S3(
    bucket="your_bucket_name",
    key=f"flows/{FLOW_NAME}.py",
    stored_as_script=True,
    local_script_path=f"{FLOW_NAME}.py",
)
RUN_CONFIG = ECSRun(
    labels=["prod"],
    task_definition=dict(
        family=FLOW_NAME,
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu=1024,
        memory=2048,
        taskRoleArn=f"arn:aws:iam::{ACCOUNT_ID}:role/prefectTaskRole",
        executionRoleArn=f"arn:aws:iam::{ACCOUNT_ID}:role/prefectECSAgentTaskExecutionRole",
        containerDefinitions=[
            dict(
                name="flow",
                image=f"{ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/your_image_name:latest",
            )
        ],
    ),
    run_task_kwargs=dict(cluster="prefectEcsCluster"),
)


@task
def say_hi():
    logger = prefect.context.get("logger")
    logger.info("Hi from Prefect %s from flow %s", prefect.__version__, FLOW_NAME)


with Flow(FLOW_NAME, storage=STORAGE, run_config=RUN_CONFIG,) as flow:
    say_hi()


```

[1]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition

[2]: https://docs.aws.amazon.com/AmazonECS/latest/userguide/task-cpu-memory-error.html

[3]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task


---
<br>

 ## VertexRun
 <div class='class-sig' id='prefect-run-configs-vertex-vertexrun'><p class="prefect-sig">class </p><p class="prefect-class">prefect.run_configs.vertex.VertexRun</p>(env=None, labels=None, image=None, machine_type=&quot;e2-standard-4&quot;, scheduling=None, service_account=None, network=None, worker_pool_specs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/run_configs/vertex.py#L6">[source]</a></span></div>

Configure a flow-run to run as a Vertex CustomJob.

The most common configuration is for the run to use a single machine, and prefect will provide a default workerPoolSpec from the machine_type argument. But this can be customized by providing the worker_pool_spec arg with the content described in [workerPoolSpec][1]. Prefect will always provide the container spec for the 0th workerPoolSpec, which is used to actually run the flow

**Args**:     <ul class="args"><li class="args">`env (dict, optional)`: Additional environment variables to set.     </li><li class="args">`labels (Iterable[str], optional)`: an iterable of labels to apply to this         run config. Labels are string identifiers used by Prefect Agents         for selecting valid flow runs when polling for work     </li><li class="args">`image (str, optional)`: The image to use for this task. If not         provided, will be either inferred from the flow's storage (if using         `Docker` storage), or use the default configured on the agent.     </li><li class="args">`machine_type (str, optional)`: The machine type to use for the run,         which controls the available CPU and memory. See [machine_types][2]         for valid choices.     </li><li class="args">`scheduling (dictionary, optional)`: The scheduling for the custom job, which         can be used to set a timeout (maximum run time). See         [CustomJobSpec][1] for the expected format.     </li><li class="args">`service_account (str, optional)`: Specifies the service account to use         as the run-as account in vertex. The agent submitting jobs must have         act-as permission on this run-as account. If unspecified, the AI         Platform Custom Code Service Agent for the CustomJob's project is         used.     </li><li class="args">`network (str, optional)`: The full name of the Compute Engine network         to which the Job should be peered. Private services access must         already be configured for the network. If left unspecified, the job         is not peered with any network.     </li><li class="args">`worker_pool_specs (list, optional)`: The full worker pool specs         for the custom job, which can be used for advanced configuration.         If provided, it will overwrite the default constructed from the         machine type arg.</li></ul>

**Examples**:

Use the defaults set on the agent:


```python
flow.run_config = VertexRun()

```

Use the default task definition, but override the image and machine type:


```python
flow.run_config = VertexRun(
    image="example/my-custom-image:latest",
    machine_type="e2-highmem-8",
)

```

[1]: https://cloud.google.com/vertex-ai/docs/reference/rest/v1/CustomJobSpec [2]: https://cloud.google.com/vertex-ai/docs/training/configure-compute#machine-types


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>
