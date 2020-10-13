from prefect import Task
from prefect.client import Client
from typing import Any
import prefect


class CancelFlowRunTask(Task):
    """
    Task to cancel a running flow.

    Args:
        - flow_run_id (str, optional): The ID of the flow run to cancel
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        flow_run_id: str = None,
        **kwargs: Any,
    ):
        self.flow_run_id = flow_run_id
        super().__init__(**kwargs)

    def run(self, flow_run_id: str = None):
        """
        Args:
            - flow_run_id (str, optional): The ID of the flow run to cancel

        Returns:
            - bool: Boolean representing whether the flow run was canceled successfully or not
        """
        # if id is not provided, use current flow id
        if flow_run_id is None:
            flow_run_id = prefect.context["flow_run_id"]
        if flow_run_id is None:
            raise ValueError("Can't delete a flow without flow ID. Provide flow ID.")
        client = Client()
        return client.cancel_flow_run(flow_run_id)
