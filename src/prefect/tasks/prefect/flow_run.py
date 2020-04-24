from typing import Any
from urllib.parse import urlparse

from prefect import config, Task
from prefect.client import Client
from prefect.utilities.graphql import EnumValue, with_args
from prefect.utilities.tasks import defaults_from_attrs


class FlowRunTask(Task):
    """
    Task used to kick off a flow run using Prefect Core's server or Prefect Cloud.
    If multiple versions of the flow are found, this task will kick off the most recent unarchived version.

    Args:
        - flow_name (str, optional): the name of the flow to schedule; this value may also be provided at run time
        - project_name (str, optional): the Cloud project in which the flow is located; this value may also be provided
            at run time
        - parameters (dict, optional): the parameters to pass to the flow run being scheduled; this value may also
            be provided at run time
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        flow_name: str = None,
        project_name: str = None,
        parameters: dict = None,
        **kwargs: Any
    ):
        self.flow_name = flow_name
        self.project_name = project_name
        self.parameters = parameters
        super().__init__(**kwargs)

    @defaults_from_attrs("flow_name", "project_name", "parameters")
    def run(
        self, flow_name: str = None, project_name: str = None, parameters: dict = None
    ) -> str:
        """
        Run method for the task; responsible for scheduling the specified flow run.

        Args:
            - flow_name (str, optional): the name of the flow to schedule; if not provided, this method will
                use the flow name provided at initialization
            - project_name (str, optional): the Cloud project in which the flow is located; if not provided, this method
                will use the project provided at initialization
            - parameters (dict, optional): the parameters to pass to the flow run being scheduled; if not provided,
                this method will use the parameters provided at initialization

        Returns:
            - str: the ID of the newly-scheduled flow run

        Raises:
            - ValueError: if flow or project names were not provided, or if the flow provided cannot be found

        Example:
            ```python
            from prefect.tasks.prefect.flow_run import FlowRunTask

            kickoff_task = FlowRunTask(project_name="My Cloud Project", flow_name="My Cloud Flow")
            ```

        """
        # verify that flow and project names were passed in some capacity or another
        if flow_name is None:
            raise ValueError("Must provide a flow name.")
        if project_name is None and "prefect.io" in urlparse(config.cloud.api).netloc:
            raise ValueError("Must provide a project name.")

        where_clause = {
            "name": {"_eq": flow_name},
            "archived": {"_eq": False},
        }

        if project_name:
            where_clause["project"] = {"name": {"_eq": project_name}}

        # find the flow ID to schedule
        query = {
            "query": {
                with_args(
                    "flow",
                    {
                        "where": where_clause,
                        "order_by": {"version": EnumValue("desc")},
                        "limit": 1,
                    },
                ): {"id"}
            }
        }

        client = Client()
        flow = client.graphql(query).data.flow

        # verify that a flow has been returned
        if not flow:
            raise ValueError("Flow '{}' not found.".format(flow_name))

        # grab the ID for the most recent version
        flow_id = flow[0].id
        return client.create_flow_run(flow_id=flow_id, parameters=parameters)
