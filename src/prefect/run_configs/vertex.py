from typing import Iterable, List

from prefect.run_configs.base import RunConfig


class VertexRun(RunConfig):
    """Configure a flow-run to run as a Vertex CustomJob.

    The most common configuration is for the run to use a single machine, and
    prefect will provide a default workerPoolSpec from the machine_type
    argument. But this can be customized by providing the worker_pool_spec arg
    with the content described in [workerPoolSpec][1]. Prefect will always
    provide the container spec for the 0th workerPoolSpec, which is used to
    actually run the flow

    Args:
        - env (dict, optional): Additional environment variables to set.
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work
        - image (str, optional): The image to use for this task. If not
            provided, will be either inferred from the flow's storage (if using
            `Docker` storage), or use the default configured on the agent.
        - machine_type (str, optional): The machine type to use for the run,
            which controls the available CPU and memory. See [machine_types][2]
            for valid choices.
        - scheduling (dictionary, optional): The scheduling for the custom job, which
            can be used to set a timeout (maximum run time). See
            [CustomJobSpec][1] for the expected format.
        - service_account (str, optional): Specifies the service account to use
            as the run-as account in vertex. The agent submitting jobs must have
            act-as permission on this run-as account. If unspecified, the AI
            Platform Custom Code Service Agent for the CustomJob's project is
            used.
        - network (str, optional): The full name of the Compute Engine network
            to which the Job should be peered. Private services access must
            already be configured for the network. If left unspecified, the job
            is not peered with any network.
        - worker_pool_specs (list, optional): The full worker pool specs
            for the custom job, which can be used for advanced configuration.
            If provided, it will overwrite the default constructed from the
            machine type arg.


    Examples:

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

    [1]: https://cloud.google.com/vertex-ai/docs/reference/rest/v1/\
CustomJobSpec
    [2]: https://cloud.google.com/vertex-ai/docs/training/\
configure-compute#machine-types

    """

    # TODO ADD GPUS SUPPORT
    def __init__(
        self,
        *,
        env: dict = None,
        labels: Iterable[str] = None,
        image: str = None,
        machine_type: str = "e2-standard-4",
        scheduling: dict = None,
        service_account: str = None,
        network: str = None,
        worker_pool_specs: List[dict] = None,
    ) -> None:
        super().__init__(env=env, labels=labels)
        self.image = image
        self.machine_type = machine_type
        self.scheduling = scheduling
        self.service_account = service_account
        self.network = network
        self.worker_pool_specs = worker_pool_specs
