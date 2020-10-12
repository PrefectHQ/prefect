import json
import importlib.resources as resources

import boto3
from botocore.exceptions import WaiterError
from botocore.waiter import WaiterModel, create_waiter_with_client

from prefect.tasks.aws import waiters
from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


class AWSClientWait(Task):
    """
    Task for waiting on a long-running AWS job. Uses the underlying boto3 waiter functionality.


    Args:
        - client (str, optional): The AWS client on which to wait (e.g., 'batch', 'ec2', etc)
        - waiter_name (str, optional): The name of the waiter to instantiate. Can be a boto-supported
            waiter or one of prefect's custom waiters
        - waiter_definition (dict, optional): A valid custom waiter model, as a dict.
        - boto_kwargs (dict, optional): additional kekyword arguments to forward to the boto client.
    """

    def __init__(
        self,
        client: str = None,
        waiter_name: str = None,
        waiter_definition: dict = None,
        boto_kwargs: dict = None,
        **kwargs,
    ):
        self.client = client
        self.waiter_name = waiter_name
        self.waiter_definition = waiter_definition
        self.boto_kwargs = {} if boto_kwargs is None else boto_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("client", "waiter_name", "waiter_definition")
    def run(
        self,
        client: str,
        waiter_name: str,
        waiter_definition: dict = None,
        waiter_kwargs: dict = None,
        credentials: str = None,
    ):
        """
        Task for waiting on a long-running AWS job. Uses the underlying boto3 waiter functionality.


        Args:
            - client (str): The AWS client on which to wait (e.g., 'batch', 'ec2', etc)
            - waiter_name (str): The name of the waiter to instantiate. In addition to the full list of
                boto3-supported waiters, Prefect supports the following waiters:

                    - "JobExists" (batch): Wait until an AWS batch job has been instantiated.
                    - "JobRunning" (batch): Wait until an AWS batch job has begun running.
                    - "JobComplete" (batch): Wait until an AWS batch job has completed successfully.

                You may also use a custom waiter name, if you supply an accompanying waiter_definition
                dict.

            - waiter_definition (dict, optional): A valid custom waiter model, as a dict. Note that if
                you supply a custom definition, it is assumed that the provided 'waiter_name' is
                contained within the waiter_definition dict.
            - waiter_kwargs (dict, optional): Arguments to pass to the `waiter.wait(...)` method. Will
                depend upon the specific waiter being called.
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
        """
        if not (client and waiter_name):
            raise ValueError("Must provide both a client and waiter_name.")

        if not waiter_kwargs:
            waiter_kwargs = {}

        boto_client = get_boto_client(
            client, credentials=credentials, **self.boto_kwargs
        )
        if waiter_definition:
            # Use user-provided waiter definition
            waiter_model = WaiterModel(waiter_definition)
            waiter = create_waiter_with_client(waiter_name, waiter_model, boto_client)
        else:
            # Use either boto-provided or prefect-provided waiter
            if waiter_name in boto_client.waiter_names:
                waiter = boto_client.get_waiter(waiter_name)
            else:
                waiter = self._load_prefect_waiter(boto_client, client, waiter_name)

        try:
            waiter.wait(**waiter_kwargs)
        except WaiterError as e:
            raise FAIL(f"AWS {client} waiter '{waiter_name}' failed with: {str(e)}")

    @staticmethod
    def _load_prefect_waiter(
        boto_client: "boto3.client", client_str: str, waiter_name: str
    ):
        """
        Load a custom waiter from the ./waiters directory.
        """
        try:
            # Instantiate waiter from accompanying client json file
            with resources.open_text(waiters, f"{client_str}.json") as handle:
                waiter_model = WaiterModel(json.load(handle))

            return create_waiter_with_client(waiter_name, waiter_model, boto_client)
        except Exception:
            raise ValueError(
                f"Unable to load waiter '{waiter_name}' for AWS client '{client_str}'."
            )
