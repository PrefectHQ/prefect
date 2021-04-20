from typing import Union, List

import prefect
from prefect.serialization.flow import FlowSchema
from prefect.utilities.graphql import with_args
from prefect.utilities.logging import get_logger


logger = get_logger("api.flow")


class FlowMetadata:
    def __init__(
        self,
        flow_id: str,
        flow: "prefect.Flow",
        settings: dict,
        run_config: dict,
        serialized_flow: dict,
        archived: bool,
        project_name: str,
        core_version: str,
        storage: prefect.storage.Storage,
        name: str,
    ):
        self.flow_id = flow_id
        self.flow = flow
        self.settings = settings
        self.run_config = run_config
        self.serialized_flow = serialized_flow
        self.archived = archived
        self.project_name = project_name
        self.core_version = core_version
        self.storage = storage
        self.name = name

    @classmethod
    def from_flow_data(cls, flow_data: dict) -> "FlowMetadata":

        flow_id = flow_data.pop("id")
        project_name = flow_data.pop("project")["name"]
        deserialized_flow = FlowSchema().load(data=flow_data["serialized_flow"])
        storage = prefect.serialization.storage.StorageSchema().load(
            flow_data.pop("storage")
        )

        return cls(
            flow_id=flow_id,
            project_name=project_name,
            flow=deserialized_flow,
            storage=storage,
            **flow_data,
        )

    @classmethod
    def from_flow_id(cls, flow_id: str = None) -> "FlowMetadata":
        if not isinstance(flow_id, str):
            raise TypeError(
                f"Unexpected type {type(flow_id)!r} for `flow_id`, " f"expected 'str'."
            )

        return cls.from_flow_data(cls.query_for_flows(where={"id": {"_eq": flow_id}}))

    @classmethod
    def from_flow_name(cls, flow_name: str, project_name: str = None) -> "FlowMetadata":
        return cls.from_flow_data(
            cls.query_for_flows(
                where={
                    "name": {"_eq": flow_name},
                    "project": {"name": {"_eq": project_name}},
                }
            )
        )

    @staticmethod
    def query_for_flows(
        where: dict,
        many: bool = False,
        order_by: dict = None,
        error_on_empty: bool = True,
    ) -> Union[dict, List[dict]]:
        """
        Query for task run data necessary to initialize `Flow` instances
        with `Flow.from_flow_data`.

        Args:
            where (required): The Hasura `where` clause to filter by
            many (optional): Are many results expected? If `False`, a single record will
                be returned and if many are found by the `where` clause an exception
                will be thrown. If `True` a list of records will be returned.
            order_by (optional): An optional Hasura `order_by` clause to order results
                by. Only applicable when `many` is `True`
            error_on_empty (optional): If `True` and no tasks are found, a `ValueError`
                will be raised. If `False`, an empty list or dict will be returned
                based on the value of `many`.

        Returns:
            A dict of task run information (or a list of dicts if `many` is `True`)
        """
        client = prefect.Client()

        query_args = {"where": where}
        if order_by is not None:
            query_args["order_by"] = order_by

        flow_query = {
            "query": {
                with_args("flow", query_args): {
                    "id": True,
                    "settings": True,
                    "run_config": True,
                    "serialized_flow": True,
                    "name": True,
                    "archived": True,
                    "project": {"name"},
                    "core_version": True,
                    "storage": True,
                }
            }
        }

        result = client.graphql(flow_query)
        flows = result.get("data", {}).get("flow", None)

        if flows is None:
            raise ValueError(
                f"Received bad result while querying for flows where {where}: "
                f"{result}"
            )

        if len(flows) > 1 and not many:
            raise ValueError(
                f"Found multiple ({len(flows)}) flows while querying for flows "
                f"where {where}: {flows}"
            )

        if not flows:  # Empty list
            if error_on_empty:
                raise ValueError(
                    f"No results found while querying for flows where {where}"
                )
            return [] if many else {}

        # Return a dict
        if not many:
            flow = flows[0]
            return flow

        # Return a list
        return flows
