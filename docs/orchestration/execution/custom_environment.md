# Custom Environment

::: warning
Flows configured with environments are being deprecated - we recommend users
transition to using "Run Configs" instead. See [flow
configuration](/orchestration/flow_config/overview.md) and [upgrading
tips](/orchestration/flow_config/upgrade.md) for more information.
:::

[[toc]]

Prefect environments allow for completely custom, user-created environments. The only requirement is that your custom environment inherit from the base `Environment` class.

### Process

Custom environments can be attached to flows in the same manner as any preexisting Prefect environment, and are stored in the storage option alongside your flow. It will never be sent to the Prefect API and will only exist inside your Flow's storage.

:::warning Custom Environment Naming
Make sure the name of your custom environment does not match the names of any preexisting [Prefect environments](/api/latest/environments/execution.html) because it could behave unpredictably when working with Prefect Serializers.
:::

### Custom Environment Example

```python
from typing import Any, Callable, List

from prefect import config
from prefect.environments.execution import Environment
from prefect.storage import Storage


class MyCustomEnvironment(Environment):
    """
    MyCustomEnvironment is my environment that uses the default executor to run a Flow.

    Args:
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
    """

    def __init__(
        self,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
    ) -> None:
        super().__init__(labels=labels, on_start=on_start, on_exit=on_exit)

    # Optionally specify any required dependencies
    # that will be checked for during the deployment healthchecks
    @property
    def dependencies(self) -> list:
        return []

    def setup(self, storage: "Storage") -> None:
        """
        Sets up any infrastructure needed for this Environment

        Args:
            - storage (Storage): the Storage object that contains the flow
        """
        # Do some set up here if needed, otherwise pass
        pass

    def execute(  # type: ignore
        self, storage: "Storage", flow_location: str, **kwargs: Any
    ) -> None:
        """
        Run a flow from the `flow_location` here using the default executor

        Args:
            - storage (Storage): the storage object that contains information relating
                to where and how the flow is stored
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """

        # Call on_start callback if specified
        if self.on_start:
            self.on_start()

        try:
            from prefect.engine import (
                get_default_executor_class,
                get_default_flow_runner_class,
            )

            # Load serialized flow from file and run it with a DaskExecutor
            flow = storage.get_flow(flow_location)

            # Get default executor and flow runner
            executor = get_default_executor_class()
            runner_cls = get_default_flow_runner_class()

            # Run flow
            runner_cls(flow=flow).run(executor=executor)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc
        finally:
            # Call on_exit callback if specified
            if self.on_exit:
                self.on_exit()


# ###################### #
#          FLOW          #
# ###################### #


from prefect import task, Flow
from prefect.storage import Docker


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Custom Environment Example",
    environment=MyCustomEnvironment(),  # Use our custom Environment
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="custom-env-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
