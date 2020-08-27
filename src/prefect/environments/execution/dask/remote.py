import warnings
from typing import Callable, List

from distributed.security import Security

from prefect.environments.execution.remote import RemoteEnvironment


class RemoteDaskEnvironment(RemoteEnvironment):
    """
    RemoteDaskEnvironment is an environment which takes the address of an existing
    Dask cluster and runs the flow on that cluster using `DaskExecutor`.

    Example:
    ```python
    # using a RemoteDaskEnvironment with an existing Dask cluster

    env = RemoteDaskEnvironment(
        address="tcp://dask_scheduler_host_or_ip:8786"
    )

    f = Flow("dummy flow", environment=env)
    ```

    If using the Security object then it should be filled out like this:

    ```python
    security = Security(tls_ca_file='cluster_ca.pem',
                        tls_client_cert='cli_cert.pem',
                        tls_client_key='cli_key.pem',
                        require_encryption=True)
    ```

    For more on using TLS with Dask see https://distributed.dask.org/en/latest/tls.html


    Args:
        - address (str): an address of the scheduler of a Dask cluster in URL form,
            e.g. `tcp://172.33.17.28:8786`
        - security (Security, optional): a Dask Security object from
          `distributed.security.Security`.  Use this to connect to a Dask cluster that is
          enabled with TLS encryption.
        - executor_kwargs (dict, optional): a dictionary of kwargs to be passed to
            the executor; defaults to an empty dictionary
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the
            flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow
            finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this environment
    """

    def __init__(
        self,
        address: str,
        security: Security = None,
        executor_kwargs: dict = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
    ) -> None:
        if type(self) is RemoteDaskEnvironment or not type(self).__module__.startswith(
            "prefect."
        ):
            # Only warn if its a subclass not part of prefect, since we don't
            # want to update the code for e.g. `DaskCloudProviderEnvironment`
            warnings.warn(
                "`RemoteDaskEnvironment` is deprecated, please use `LocalEnvironment` with a "
                "`DaskExecutor` instead.",
                stacklevel=2,
            )
        self.address = address
        dask_executor_kwargs = executor_kwargs or dict()
        dask_executor_kwargs["address"] = address

        if security:
            dask_executor_kwargs["security"] = security

        super().__init__(
            executor="prefect.engine.executors.DaskExecutor",
            executor_kwargs=dask_executor_kwargs,
            labels=labels,
            on_start=on_start,
            on_exit=on_exit,
            metadata=metadata,
        )

    @property
    def dependencies(self) -> list:
        return []
