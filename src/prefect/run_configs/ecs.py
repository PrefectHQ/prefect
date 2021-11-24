from typing import Union, Iterable

import yaml

from prefect.run_configs.base import RunConfig
from prefect.utilities.filesystems import parse_path


class ECSRun(RunConfig):
    """Configure a flow-run to run as an ECS Task.

    ECS Tasks are composed of task definitions and runtime parameters.

    Task definitions can be configured using either the `task_definition`,
    `task_definition_path`, or `task_definition_arn` parameters. If neither is
    specified, the default configured on the agent will be used. At runtime
    this task definition will be registered once per flow version - subsequent
    runs of the same flow version will reuse the existing definition.

    Runtime parameters can be specified via `run_task_kwargs`. These will be
    merged with any runtime parameters configured on the agent when starting
    the task.

    Note that certain Prefect specific environment variables defined within the
    `task_definition` will be overwritten by the ECS Agent when a new task is
    run (see method get_run_task_kwargs of the ECSAgent). For example,
    although the variable `PREFECT__LOGGING__LEVEL` might be defined within
    `containerDefinitions` (of the `task_definition`), it will first be
    ovewritten with the Prefect config and then by `env` (if defined). Therefore,
    do not set any Prefect specific environment variables within `task_definition`,
    `task_definition_path` or `task_definition_arn`. Instead, use the top-level
    `ECSRun.env` setting.

    Args:
        - task_definition (dict, optional): An in-memory task definition spec
            to use. The flow will be executed in a container named `flow` - if
            a container named `flow` isn't part of the task definition, Prefect
            will add a new container with that name.  See the
            [ECS.Client.register_task_definition][1] docs for more information
            on task definitions. Note that this definition will be stored
            directly in Prefect Cloud/Server - use `task_definition_path`
            instead if you wish to avoid this.
        - task_definition_path (str, optional): Path to a task definition spec
            to use. If you started your agent in a local process (with
            `prefect agent ecs start --label your-label`), then you can reference a path
            on that machine (use either no file scheme, or a `file`/`local` scheme).
            The task definition will then be loaded on initialization
            and stored on the `ECSRun` object as the `task_definition` field.
            Otherwise the task definition will be loaded at runtime on the
            agent.  Supported runtime file schemes include `s3`, `gcs`, and
            `agent` (for paths local to the runtime agent).
        - task_definition_arn (str, optional): A pre-registered task definition
            ARN to use (either `family:revision`, or a full task
            definition ARN). This task definition must include a container
            named `flow` (which will be used to run the flow).
        - image (str, optional): The image to use for this task. If not
            provided, will be either inferred from the flow's storage (if using
            `Docker` storage), or use the default configured on the agent. Note that
            when using an ECR image, you need to explicitly provide the
            `execution_role_arn`, unless you set this role explicitly in a custom `task_definition`.
            This means: either you provide a custom `task_definition` that contains
            both the image and `execution_role_arn` (with ECR permissions),
            or you provide both a custom `image` and an `execution_role_arn`
            simultaneously.
        - env (dict, optional): Additional environment variables to set on the task.
        - cpu (int or str, optional): The amount of CPU available to the task. Can
            be ether an integer in CPU units (e.g. `1024`), or a string using
            vCPUs (e.g. `"1 vcpu"`). Note that ECS imposes strict limits on
            what values this can take, see the [ECS documentation][2] for more
            information.
        - memory (int or str, optional): The amount of memory available to the
            task. Can be ether an integer in MiB (e.g. `1024`), or a string
            with units (e.g. `"1 GB"`). Note that ECS imposes strict limits on
            what values this can take, see the [ECS documentation][2] for more
            information.
        - task_role_arn (str, optional): The full ARN of the IAM role
            to use for this task. If you provide a custom `task_definition` that
            already contains the `task_role_arn`, then you can skip this argument.
            You can also skip it when your flow doesn't need access to any AWS
            resources such as S3. But if you use S3 storage (or results) and you don't set
            a custom `task_definition`, this role must be set explicitly.
        - execution_role_arn (str, optional): The execution role ARN to use
            when registering a task definition for this task. If you provide a custom
            `task_definition` that already contains the `execution_role_arn`, then you
            can skip this argument. But if you don't set any custom `task_definition`,
            and you supply an ECR `image`, then you need to set an `execution_role_arn`
            explicitly to grant ECR access.
        - run_task_kwargs (dict, optional): Additional keyword arguments to
            pass to `run_task` when starting this task. It should be used only for
            runtime-specific arguments such as `cpu`, `memory`, `cluster`, or `launchType`,
            rather than `task_definition`-specific arguments.
            See the [ECS.Client.run_task][3] docs for more information.
        - labels (Iterable[str], optional): An iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work

    Examples:

    1) Use the defaults set on the agent (assuming label "prod"):

    ```python
    flow.run_config = ECSRun(labels=["prod"])
    ```

    2) Use a custom task definition uploaded to S3 as a YAML file. This task definition contains
    a container named "flow", as well as a custom execution role and task role. The flow should
    be picked up for execution by an agent with label "prod" and should be deployed to a cluster
    called "prefectEcsCluster".

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

    3) Use a custom pre-registered task definition (referenced by `family:revision`
    or by a full ARN), then deploy the flow to a cluster called "prefectEcsCluster":

    ```python
    flow.run_config = ECSRun(
        labels=["prod"],
        task_definition_arn="prefectFlow:1",
        # or using a full ARN:
        # task_definition_arn="arn:aws:ecs:us-east-1:XXX:task-definition/prefectFlow:1"
        run_task_kwargs=dict(cluster="prefectEcsCluster"),
    )
    ```

    4) Let Prefect register a new task definition for a flow with S3 storage and a custom
    ECR image:

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

    6) Use an explicit task definition stored in S3 as a YAML file,
    but override the image and CPU:

    ```python
    flow.run_config = ECSRun(
        task_definition="s3://bucket/flow_task_definition.yaml",
        image="XXXX.dkr.ecr.us-east-1.amazonaws.com/image_name:latest",
        cpu="2 vcpu",
    )
    ```

    7) An example flow showing ECSRun with a `task_definition` defined as dictionary,
    and S3 storage:
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

    [1]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/\
ecs.html#ECS.Client.register_task_definition

    [2]: https://docs.aws.amazon.com/AmazonECS/latest/userguide/task-cpu-memory-error.html

    [3]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/\
ecs.html#ECS.Client.run_task
    """

    def __init__(
        self,
        *,
        task_definition: dict = None,
        task_definition_path: str = None,
        task_definition_arn: str = None,
        image: str = None,
        env: dict = None,
        cpu: Union[int, str] = None,
        memory: Union[int, str] = None,
        task_role_arn: str = None,
        execution_role_arn: str = None,
        run_task_kwargs: dict = None,
        labels: Iterable[str] = None,
    ) -> None:
        super().__init__(env=env, labels=labels)

        if (
            sum(
                [
                    task_definition is not None,
                    task_definition_path is not None,
                    task_definition_arn is not None,
                ]
            )
            > 1
        ):
            raise ValueError(
                "Can only provide one of `task_definition`, `task_definition_path`, "
                "or `task_definition_arn`"
            )
        if task_definition_arn is not None and image is not None:
            raise ValueError(
                "Cannot provide both `task_definition_arn` and `image`, since an ECS "
                "task's `image` can only be configured as part of the task definition"
            )

        if task_definition_path is not None:
            parsed = parse_path(task_definition_path)
            if parsed.scheme == "file":
                with open(parsed.path) as f:
                    task_definition = yaml.safe_load(f)
                    task_definition_path = None

        if cpu is not None:
            cpu = str(cpu)
        if memory is not None:
            memory = str(memory)

        self.task_definition = task_definition
        self.task_definition_path = task_definition_path
        self.task_definition_arn = task_definition_arn
        self.image = image
        self.cpu = cpu
        self.memory = memory
        self.task_role_arn = task_role_arn
        self.execution_role_arn = execution_role_arn
        self.run_task_kwargs = run_task_kwargs
