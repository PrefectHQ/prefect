from typing import Any, TYPE_CHECKING

from prefect.storage.base import Storage
from prefect.utilities.storage import extract_flow_from_module

if TYPE_CHECKING:
    from prefect import Flow


class Module(Storage):
    """
    A Prefect Storage class for referencing flows that can be imported from a
    python module.

    Args:
        - module (str): The module to import the flow from.
        - **kwargs (Any, optional): any additional `Storage` options.

    Example:

    Suppose you have a python module `myproject.flows` that contains all your
    Prefect flows. If this module is installed and available in your execution
    environment you can use `Module` storage to reference and load the flows.

    ```python
    from prefect import Flow
    from prefect.storage import Module

    flow = Flow("module storage example")
    flow.storage = Module("myproject.flows")

    # Tip: you can use `__name__` to automatically reference the current module
    flow.storage = Module(__name__)
    ```
    """

    def __init__(self, module: str, **kwargs: Any) -> None:
        self.module = module
        super().__init__(**kwargs)

    def get_flow(self, flow_name: str) -> "Flow":
        """
        Given a flow name within this Storage object, load and return the Flow.

        Args:
            - flow_name (str): the name of the flow to return.

        Returns:
            - Flow: the requested flow
        """
        if flow_name not in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        return extract_flow_from_module(module_str=self.module, flow_name=flow_name)

    def add_flow(self, flow: "Flow") -> str:
        """
        Add a new flow to this storage object.

        Args:
            - flow (Flow): the Prefect Flow to add.

        Returns:
            - str: the location of the newly added flow in this Storage object
        """
        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )

        self.flows[flow.name] = self.module
        self._flows[flow.name] = flow
        return self.module
