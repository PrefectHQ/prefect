from typing import Union, Iterable

from prefect.run_configs.base import RunConfig


class ECSRun(RunConfig):
    """Configure a flow-run to run as an ECS Task.

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    ECS Tasks are composed of task definitions and runtime parameters. An
    `ECSRun` object is used to configure the latter only. The task definitions
    themselves are either managed by the Prefect ECS Agent or will need to be
    registered manually external to Prefect.

    Args:
        - task_definition (str, optional): The task definition to use for this
            task. Can provide either the `family:revision`, just the `family`
            (in which case the latest active revision is used), or the full
            task definition ARN. If not provided, the default task definition
            on the agent is used.
        - image (str, optional): The image to use for this task. If not
            provided, will be either inferred from the flow's storage (if using
            `Docker` storage), or use the default configured on the agent.
        - env (dict, optional): Additional environment variables to set on the task.
        - cpu (int or str, optional): The amount of CPU available to the task. Can
            be ether an integer in CPU units (e.g. `1024`), or a string using
            vCPUs (e.g. `"1 vcpu"`). If provided, this will override the
            task-level CPU settings when starting the task. Note that ECS
            imposes strict limits on what values this can take, see the [ECS
            documentation][1] for more information.
        - memory (int or str, optional): The amount of memory available to the
            task. Can be ether an integer in MiB (e.g. `1024`), or a string
            with units (e.g. `"1 GB"`). If provided, this will override the
            task-level memory settings when starting the task. Note that ECS
            imposes strict limits on what values this can take, see the [ECS
            documentation][1] for more information.
        - run_task_kwargs (dict, optional): Additional keyword arguments to
            pass to `run_task` when starting this task. See the
            [ECS.Client.run_task][2] docs for more information.
        - labels (Iterable[str], optional): An iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work

    Examples:

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

    Use an explicit task definition, and also configure some overrides to pass
    to `run_task`:

    ```python
    flow.run_config = ECSRun(
        task_definition="my-task-definition:1",
        run_task_kwargs={"overrides": {"taskRoleArn": "..."}},
    )
    ```

    [1]: https://docs.aws.amazon.com/AmazonECS/latest/userguide/task-cpu-memory-error.html

    [2]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/\
ecs.html#ECS.Client.run_task
    """

    def __init__(
        self,
        *,
        task_definition: str = None,
        image: str = None,
        env: dict = None,
        cpu: Union[int, str] = None,
        memory: Union[int, str] = None,
        run_task_kwargs: dict = None,
        labels: Iterable[str] = None,
    ) -> None:
        super().__init__(labels=labels)

        if cpu is not None:
            cpu = str(cpu)
        if memory is not None:
            memory = str(memory)

        self.task_definition = task_definition
        self.image = image
        self.env = env
        self.cpu = cpu
        self.memory = memory
        self.run_task_kwargs = run_task_kwargs
