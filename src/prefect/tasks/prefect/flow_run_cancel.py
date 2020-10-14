from prefect import Task
from prefect.client import Client
from typing import Any
import prefect


class CancelFlowRunTask(Task):
    """
    Task to cancel a flow.

    Args:
        - flow_run_id_to_cancel (str, optional): The ID of the flow to cancel
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        flow_run_id_to_cancel: str = None,
        **kwargs: Any,
    ):
        self.flow_run_id_to_cancel = flow_run_id_to_cancel
        super().__init__(**kwargs)

    def run(self, flow_run_id_to_cancel: str = None):
        """
        Args:
            - flow_run_id_to_cancel (str, optional): The ID of the flow to cancel

        Returns:
            - bool: Boolean representing whether the flow was canceled successfully or not
        """
        current_flow_run_id = prefect.context.get("flow_run_id", "")
        if current_flow_run_id == "":
            raise ValueError("Can't retrieve current flow ID.")
        # if id is not provided, use current flow id
        if self.flow_run_id_to_cancel is None:
            self.flow_run_id_to_cancel = prefect.context.get("flow_run_id", "")

        client = Client()
        return client.cancel_flow_run(self.flow_run_id_to_cancel)
