import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import azure.identity
import azure.mgmt.datafactory

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


def _get_datafactory_client(azure_credentials: Dict[str, str]):
    """
    Helper function to create datafactory client.
    """
    client_secret_credential = azure.identity.ClientSecretCredential(
        client_id=azure_credentials["client_id"],
        client_secret=azure_credentials["client_secret"],
        tenant_id=azure_credentials["tenant_id"],
    )
    subscription_id = azure_credentials["subscription_id"]
    datafactory_client = azure.mgmt.datafactory.DataFactoryManagementClient(
        client_secret_credential, subscription_id
    )
    return datafactory_client


class DatafactoryCreate(Task):
    """
    Task for creating an Azure datafactory.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - datafactory_name (str): Name of the datafactory to create.
        - resource_group_name (str): Name of the resource group.
        - azure_credentials_secret (str): Name of the Prefect Secret that stores
            your Azure credentials; This Secret must be JSON string with the keys
            `subscription_id`, `client_id`, `secret`, and `tenant`. Defaults to
            "AZ_CREDENTIALS".
        - location (str, optional): The location of the datafactory.
        - polling_interval (int, optional): The interval, in seconds, to check the provisioning
            state of the datafactory Defaults to 10.
        - options (dict, optional): The options to be passed to the
            `create_or_update` method.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """

    def __init__(
        self,
        datafactory_name: str = None,
        resource_group_name: str = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        location: str = "eastus",
        polling_interval: int = 10,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        self.datafactory_name = datafactory_name
        self.resource_group_name = resource_group_name
        self.azure_credentials_secret = azure_credentials_secret
        self.location = location
        self.polling_interval = polling_interval
        self.options = options
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "datafactory_name",
        "resource_group_name",
        "azure_credentials_secret",
        "location",
        "polling_interval",
        "options",
    )
    def run(
        self,
        datafactory_name: str = None,
        resource_group_name: str = None,
        azure_credentials_secret: str = None,
        location: Optional[str] = None,
        polling_interval: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[Any, Any]:
        """
        Create an Azure datafactory.

        Args:
            - datafactory_name (str): Name of the datafactory to create.
            - resource_group_name (str): Name of the resource group.
            - azure_credentials_secret (str): Name of the Prefect Secret that stores
                your Azure credentials; This Secret must be JSON string with the keys
                `subscription_id`, `client_id`, `secret`, and `tenant`. Defaults to
                "AZ_CREDENTIALS".
            - location (str, optional): The location of the datafactory.
            - polling_interval (int, optional): The interval, in seconds, to check the provisioning
            state of the datafactory Defaults to 10.
            - options (dict, optional): The options to be passed to the
                `create_or_update` method.

        Returns:
            The datafactory name.
        """
        if not datafactory_name:
            raise ValueError("The datafactory_name must be specified.")
        if not resource_group_name:
            raise ValueError("The resource_group_name must be specified.")

        azure_credentials = Secret(azure_credentials_secret).get()
        datafactory_client = _get_datafactory_client(azure_credentials)

        self.logger.info(
            f"Preparing to create the {datafactory_name} datafactory under "
            f"{resource_group_name} in {location}"
        )
        factory = azure.mgmt.datafactory.models.Factory(location=location)
        create_factory = datafactory_client.factories.create_or_update(
            resource_group_name, datafactory_name, factory, **options or {}
        )
        while create_factory.provisioning_state != "Succeeded":
            self.logger.info(
                f"The {datafactory_name} factory status: "
                f"{create_factory.provisioning_state}"
            )
            if create_factory.provisioning_state == "Failed":
                raise RuntimeError(
                    f"Failed to provision the {datafactory_name} factory"
                )
            time.sleep(polling_interval)

        return datafactory_name


class PipelineCreate(Task):
    """
    Task for creating an Azure datafactory pipeline.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - datafactory_name (str): Name of the datafactory to create.
        - resource_group_name (str): Name of the resource group.
        - pipeline_name (str): Name of the pipeline.
        - activities (list): The list of activities to run in the pipeline.
        - azure_credentials_secret (str, optional): Name of the Prefect Secret that stores
            your Azure credentials; This Secret must be JSON string with the keys
            `subscription_id`, `client_id`, `secret`, and `tenant`. Defaults to
            "AZ_CREDENTIALS".
        - parameters (dict): The parameters to be used in pipeline.
        - options (dict, optional): The options to be passed to the
            `create_or_update` method.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """

    def __init__(
        self,
        datafactory_name: str = None,
        resource_group_name: str = None,
        pipeline_name: str = None,
        activities: List[Any] = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        parameters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        self.datafactory_name = datafactory_name
        self.resource_group_name = resource_group_name
        self.pipeline_name = pipeline_name
        self.activities = activities
        self.azure_credentials_secret = azure_credentials_secret
        self.parameters = parameters
        self.options = options
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "datafactory_name",
        "resource_group_name",
        "pipeline_name",
        "activities",
        "azure_credentials_secret",
        "parameters",
        "options",
    )
    def run(
        self,
        datafactory_name: str = None,
        resource_group_name: str = None,
        pipeline_name: str = None,
        activities: List[Any] = None,
        azure_credentials_secret: str = None,
        parameters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[Any, Any]:
        """
        Create an Azure datafactory pipeline.

        Args:
            - datafactory_name (str): Name of the datafactory to create.
            - resource_group_name (str): Name of the resource group.
            - pipeline_name (str): Name of the pipeline.
            - activities (list): The list of activities to run in the pipeline.
            - parameters (dict): The parameters to be used in pipeline.
            - azure_credentials_secret (str, optional): Name of the Prefect Secret that stores
                your Azure credentials; This Secret must be JSON string with the keys
                `subscription_id`, `client_id`, `secret`, and `tenant`. Defaults to
                "AZ_CREDENTIALS".
            - options (dict, optional): The options to be passed to the
                `create_or_update` method.

        Returns:
            The pipeline name.
        """
        if not datafactory_name:
            raise ValueError("The datafactory_name must be specified.")
        if not resource_group_name:
            raise ValueError("The resource_group_name must be specified.")
        if not pipeline_name:
            raise ValueError("The pipeline_name must be specified.")
        if not activities:
            raise ValueError("The activities must be specified.")

        azure_credentials = Secret(azure_credentials_secret).get()
        datafactory_client = _get_datafactory_client(azure_credentials)

        self.logger.info(
            f"Preparing to create the {pipeline_name} pipeline "
            f"containing {len(activities)} activities in the "
            f"{datafactory_name} factory under {resource_group_name}."
        )
        pipeline = azure.mgmt.datafactory.models.PipelineResource(
            activities=activities, parameters=parameters or {}
        )
        datafactory_client.pipelines.create_or_update(
            resource_group_name,
            datafactory_name,
            pipeline_name,
            pipeline,
            **options or {},
        )

        return pipeline_name


class PipelineRun(Task):
    """
    Task for creating an Azure datafactory pipeline run.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - datafactory_name (str): Name of the datafactory to create.
        - resource_group_name (str): Name of the resource group.
        - pipeline_name (str): Name of the pipeline.
        - azure_credentials_secret (str, optional): Name of the Prefect Secret that stores
            your Azure credentials; This Secret must be JSON string with the keys
            `subscription_id`, `client_id`, `secret`, and `tenant`. Defaults to
            "AZ_CREDENTIALS".
        - parameters (dict, optional): The parameters to be used in pipeline.
        - polling_interval (int, optional): The interval, in seconds, to check the status of the run.
            Defaults to 10.
        - last_updated_after (datetime, optional): The time at or after which the run event
            was updated; used to filter and query the pipeline run, and defaults to yesterday.
        - last_updated_before (datetime, optional): The time at or before which the run event
            was updated; used to filter and query the pipeline run and defaults to tomorrow.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """

    def __init__(
        self,
        datafactory_name: str = None,
        resource_group_name: str = None,
        pipeline_name: str = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        parameters: Optional[Dict[str, Any]] = None,
        polling_interval: int = 10,
        last_updated_after: Optional[datetime] = None,
        last_updated_before: Optional[datetime] = None,
        **kwargs,
    ) -> None:
        self.datafactory_name = datafactory_name
        self.resource_group_name = resource_group_name
        self.pipeline_name = pipeline_name
        self.azure_credentials_secret = azure_credentials_secret
        self.parameters = parameters
        self.polling_interval = polling_interval
        self.last_updated_after = last_updated_after
        self.last_updated_before = last_updated_before
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "datafactory_name",
        "resource_group_name",
        "pipeline_name",
        "azure_credentials_secret",
        "parameters",
        "polling_interval",
        "last_updated_after",
        "last_updated_before",
    )
    def run(
        self,
        datafactory_name: str = None,
        resource_group_name: str = None,
        pipeline_name: str = None,
        azure_credentials_secret: str = None,
        parameters: Optional[Dict[str, Any]] = None,
        polling_interval: Optional[int] = None,
        last_updated_after: Optional[datetime] = None,
        last_updated_before: Optional[datetime] = None,
    ) -> Dict[Any, Any]:
        """
        Create an Azure datafactory pipeline run.

        Args:
            - datafactory_name (str): Name of the datafactory to create.
            - resource_group_name (str): Name of the resource group.
            - pipeline_name (str): Name of the pipeline.
            - azure_credentials_secret (str, optional): Name of the Prefect Secret that stores
                your Azure credentials; This Secret must be JSON string with the keys
                `subscription_id`, `client_id`, `secret`, and `tenant`. Defaults to
                "AZ_CREDENTIALS".
            - parameters (dict, optional): The parameters to be used in pipeline.
            - polling_interval (int, optional): The interval, in seconds, to check the status of the run.
                Defaults to 10.
            - last_updated_after (datetime, optional): The time at or after which the run event
                was updated; used to filter and query the pipeline run, and defaults to yesterday.
            - last_updated_before (datetime, optional): The time at or before which the run event
                was updated; used to filter and query the pipeline run and defaults to tomorrow.

        Returns:
            The pipeline run response.
        """
        if not datafactory_name:
            raise ValueError("The datafactory_name must be specified.")
        if not resource_group_name:
            raise ValueError("The resource_group_name must be specified.")
        if not pipeline_name:
            raise ValueError("The pipeline_name must be specified.")

        azure_credentials = Secret(azure_credentials_secret).get()
        datafactory_client = _get_datafactory_client(azure_credentials)
        last_updated_after = last_updated_after or datetime.utcnow() - timedelta(days=1)
        last_updated_before = last_updated_before or datetime.utcnow() + timedelta(
            days=1
        )

        self.logger.info(
            f"Preparing to run the {pipeline_name} pipeline in the "
            f"{datafactory_name} factory under {resource_group_name}."
        )
        # Create a pipeline run
        create_run = datafactory_client.pipelines.create_run(
            resource_group_name,
            datafactory_name,
            pipeline_name,
            parameters=parameters or {},
        )

        # Monitor the pipeline run
        pipeline_run = datafactory_client.pipeline_runs.get(
            resource_group_name, datafactory_name, create_run.run_id
        )
        while pipeline_run.status != "Succeeded":
            pipeline_run = datafactory_client.pipeline_runs.get(
                resource_group_name, datafactory_name, create_run.run_id
            )
            self.logger.info(f"The pipeline run status: {pipeline_run.status}")
            if pipeline_run.status.lower() not in ["queued", "inprogress", "succeeded"]:
                raise RuntimeError(pipeline_run.message)
            time.sleep(polling_interval)

        filter_params = azure.mgmt.datafactory.models.RunFilterParameters(
            last_updated_after=last_updated_after,
            last_updated_before=last_updated_before,
        )
        query_response = datafactory_client.activity_runs.query_by_pipeline_run(
            resource_group_name, datafactory_name, pipeline_run.run_id, filter_params
        )
        return query_response
