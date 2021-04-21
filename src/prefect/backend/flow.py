from typing import Union, List

import prefect
from prefect.serialization.flow import FlowSchema
from prefect.utilities.graphql import with_args, EnumValue
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
    def from_flow_obj(cls, flow: "prefect.Flow") -> "FlowMetadata":
        return cls.from_flow_data(
            cls.query_for_flows(
                where={
                    "serialized_flow": {"_eq": EnumValue("$serialized_flow")},
                    "archived": {"_eq": False},
                },
                variables={"serialized_flow": ("jsonb", flow.serialize())},
            )
        )

    @classmethod
    def from_flow_name(
        cls, flow_name: str, project_name: str = None, use_last_updated: bool = False
    ) -> "FlowMetadata":
        where = {"name": {"_eq": flow_name}, "archived": {"_eq": False}}
        if project_name is not None:
            where["project"] = {
                "name": ({"_eq": project_name} if project_name else {"_is_null": True})
            }

        flows = cls.query_for_flows(
            where=where,
            many=True,
            order_by={"updated_at": EnumValue("desc")},
        )
        if len(flows) > 1 and not use_last_updated:
            raise ValueError(
                f"Found multiple flows matching {where}. "
                f"Provide a `project_name` as well or toggle `use_last_updated` "
                f"to use the flow that was most recently updated"
            )

        flow = flows[0]
        return cls.from_flow_data(flow)

    @staticmethod
    def query_for_flows(
        where: dict,
        many: bool = False,
        order_by: dict = None,
        error_on_empty: bool = True,
        variables: Dict[str, Tuple[str, Any]] = None,
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
            variables (optional): Variables to inject into the query formatted as
                {key: (type, value)}

        Returns:
            A dict of task run information (or a list of dicts if `many` is `True`)
        """
        client = prefect.Client()

        query_args = {"where": where}
        if order_by is not None:
            query_args["order_by"] = order_by

        # Parse types from variables for "query(var_name: type)"
        variables = variables or {}
        var_types = ""
        if variables:
            var_types = (
                "("
                + ", ".join(
                    [f"${key}: {type_}" for key, (type_, _) in variables.items()]
                )
                + ")"
            )

        flow_query = {
            f"query{var_types}": {
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

        result = client.graphql(
            flow_query, variables={key: val for key, (_, val) in variables.items()}
        )
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
                    f"No results found while querying for flows where {where!r}"
                )
            return [] if many else {}

        # Return a dict
        if not many:
            flow = flows[0]
            return flow

        # Return a list
        return flows
