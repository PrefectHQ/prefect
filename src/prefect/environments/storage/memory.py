from typing import Any, Dict, Iterable, List, TYPE_CHECKING, Union

import prefect
from prefect.environments.storage import Storage

if TYPE_CHECKING:
    from prefect.core.flow import Flow
    from prefect.engine.flow_runner import FlowRunner


class Memory(Storage):
    """
    Memory Storage class, mainly used for testing.  This class represents the Storage
    interface for Flows contained in memory, i.e., flows are simply stored as attributes
    of this class.
    """

    def __init__(self) -> None:
        self.flows = dict()  # type: Dict[str, prefect.core.flow.Flow]
        super().__init__()

    def get_runner(
        self, flow_location: str, return_flow: bool = True
    ) -> Union["Flow", "FlowRunner"]:
        """
        Given a flow name, returns something capable of running the Flow.

        Args:
            - flow_location (str): the name of the flow
            - return_flow (bool, optional): whether to return the full Flow object
                or a `FlowRunner`; defaults to `True`

        Returns:
            - Union[Flow, FlowRunner]: the requested Flow or a FlowRunner for the requested Flow

        Raises:
            - ValueError: if the flow is not contained in this storage
        """
        if not flow_location in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        if return_flow:
            return self.flows[flow_location]
        else:
            runner_cls = prefect.engine.get_default_flow_runner_class()
            return runner_cls(flow=self.flows[flow_location])

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for adding a new flow to this Storage object.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object

        Raises:
            - ValueError: if a flow with the same name is already contained in this storage
        """
        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )
        self.flows[flow.name] = flow
        return flow.name

    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is contained within this storage.
        """
        if not isinstance(obj, str):
            return False
        return obj in self.flows

    def get_flow_location(self, flow_name: str) -> "Flow":
        """
        Given a flow, retrieves its location within this Storage object.

        Args:
            - flow_name (str): the name of a Prefect Flow contained within this Storage

        Returns:
            - str: the location of the Flow

        Raises:
            - ValueError: if the provided Flow does not live in this Storage object
        """
        if not flow_name in self.flows:
            raise ValueError("Flow is not contained in this Storage")

        return self.flows[flow_name]

    def build(self) -> "Storage":
        """
        Build the Storage object.

        Returns:
            - Storage: a Storage object that contains information about how and where
                each flow is stored
        """
        return self
