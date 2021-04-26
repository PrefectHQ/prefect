import warnings
from typing import Any, Dict, List

import prefect
from prefect.utilities.exceptions import ClientError
from prefect.utilities.graphql import (
    EnumValue,
    compress,
    with_args,
)
from prefect.utilities.logging import get_logger

logger = get_logger("backend.flow")


def register(
    flow: "prefect.core.Flow",
    project_name: str = None,
    build: bool = True,
    set_schedule_active: bool = True,
    version_group_id: str = None,
    compressed: bool = True,
    idempotency_key: str = None,
) -> "FlowView":
    """
    Push a new flow to Prefect Cloud

    Args:
        - flow (Flow): a flow to register
        - project_name (str, optional): the project that should contain this flow.
        - build (bool, optional): if `True`, the flow's environment is built
            prior to serialization; defaults to `True`
        - set_schedule_active (bool, optional): if `False`, will set the schedule to
            inactive in the database to prevent auto-scheduling runs (if the Flow has a
            schedule).  Defaults to `True`. This can be changed later.
        - version_group_id (str, optional): the UUID version group ID to use for versioning
            this Flow in Cloud; if not provided, the version group ID associated with this
            Flow's project and name will be used.
        - compressed (bool, optional): if `True`, the serialized flow will be; defaults to
            `True` compressed
        - idempotency_key (optional, str): a key that, if matching the most recent
            registration call for this flow group, will prevent the creation of
            another flow version and return the existing flow id instead.

    Returns:
        - str: the ID of the newly-registered flow

    Raises:
        - ClientError: if the register failed
    """
    client = prefect.backend.client.Client()

    required_parameters = {p for p in flow.parameters() if p.required}
    if flow.schedule is not None and required_parameters:
        required_names = {p.name for p in required_parameters}
        if not all(
            [
                required_names <= set(c.parameter_defaults.keys())
                for c in flow.schedule.clocks
            ]
        ):
            raise ClientError(
                "Flows with required parameters can not be scheduled automatically."
            )
    if any(e.key for e in flow.edges) and flow.result is None:
        warnings.warn(
            "No result handler was specified on your Flow. Cloud features such as "
            "input caching and resuming task runs from failure may not work properly.",
            stacklevel=2,
        )
    if compressed:
        create_mutation = {
            "mutation($input: create_flow_from_compressed_string_input!)": {
                "create_flow_from_compressed_string(input: $input)": {"id"}
            }
        }
    else:
        create_mutation = {
            "mutation($input: create_flow_input!)": {
                "create_flow(input: $input)": {"id"}
            }
        }

    project = None

    if project_name is None:
        raise TypeError("'project_name' is a required field when registering a flow.")

    query_project = {
        "query": {
            with_args("project", {"where": {"name": {"_eq": project_name}}}): {
                "id": True
            }
        }
    }

    project = self.graphql(query_project).data.project  # type: ignore

    if not project:
        raise ValueError(
            "Project {} not found. Run `prefect create project '{}'` to create it.".format(
                project_name, project_name
            )
        )

    serialized_flow = flow.serialize(build=build)  # type: Any

    # Configure environment.metadata (if using environment-based flows)
    if flow.environment is not None:
        # Set Docker storage image in environment metadata if provided
        if isinstance(flow.storage, prefect.storage.Docker):
            flow.environment.metadata["image"] = flow.storage.name
            serialized_flow = flow.serialize(build=False)

        # If no image ever set, default metadata to image on current version
        if not flow.environment.metadata.get("image"):
            version = prefect.__version__.split("+")[0]
            flow.environment.metadata["image"] = f"prefecthq/prefect:{version}"
            serialized_flow = flow.serialize(build=False)

    # verify that the serialized flow can be deserialized
    try:
        prefect.serialization.flow.FlowSchema().load(serialized_flow)
    except Exception as exc:
        raise ValueError(
            "Flow could not be deserialized successfully. Error was: {}".format(
                repr(exc)
            )
        ) from exc

    if compressed:
        serialized_flow = compress(serialized_flow)

    inputs = dict(
        project_id=(project[0].id if project else None),
        serialized_flow=serialized_flow,
        set_schedule_active=set_schedule_active,
        version_group_id=version_group_id,
    )
    # Add newly added inputs only when set for backwards compatibility
    if idempotency_key is not None:
        inputs.update(idempotency_key=idempotency_key)

    res = client.graphql(
        create_mutation,
        variables=dict(input=inputs),
        retry_on_api_error=False,
    )  # type: Any

    flow_id = (
        res.data.create_flow_from_compressed_string.id
        if compressed
        else res.data.create_flow.id
    )

    return FlowView.from_flow_id(flow_id)


class FlowView:
    """
    A view of Flow data stored in the Prefect API.

    This object is designed to be an immutable view of the data stored in the Prefect
    backend API at the time it is created

    Attributes:
        flow_id: The uuid of the flow
        flow: A deserialized copy of the flow. This is not loaded from storage, so tasks
            will not be runnable but the DAG can be explored.
        settings: A dict of flow settings
        run_config: A dict representation of the flow's run configuration
        serialized_flow: A serialized copy of the flow
        archived: A bool indicating if this flow is archived or not
        project_name: The name of the project the flow is registered to
        core_version: The core version that was used to register the flow
        storage: The deserialized Storage object used to store this flow
        name: The name of the flow
    """

    def __init__(
        self,
        flow_id: str,
        flow: "prefect.Flow",
        flow_group_id: str,
        settings: dict,
        run_config: dict,
        serialized_flow: dict,
        archived: bool,
        project_name: str,
        core_version: str,
        storage: "prefect.storage.Storage",
        name: str,
    ):
        self.flow_id = flow_id
        self.flow = flow
        self.flow_group_id = flow_group_id
        self.settings = settings
        self.run_config = run_config
        self.serialized_flow = serialized_flow
        self.archived = archived
        self.project_name = project_name
        self.core_version = core_version
        self.storage = storage
        self.name = name

    @classmethod
    def from_flow_data(cls, flow_data: dict) -> "FlowView":
        """
        Get an instance of this class given a dict of required flow data

        Handles deserializing any objects that we want real representations of
        """

        flow_id = flow_data.pop("id")
        project_name = flow_data.pop("project")["name"]
        deserialized_flow = prefect.serialization.flow.FlowSchema().load(
            data=flow_data["serialized_flow"]
        )
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
    def from_flow_id(cls, flow_id: str) -> "FlowView":
        """
        Get an instance of this class given a `flow_id` to lookup

        Args:
            flow_id: The uuid of the flow

        Returns:
            A new instance of FlowView
        """
        if not isinstance(flow_id, str):
            raise TypeError(
                f"Unexpected type {type(flow_id)!r} for `flow_id`, " f"expected 'str'."
            )

        return cls.from_flow_data(cls.query_for_flow(where={"id": {"_eq": flow_id}}))

    @classmethod
    def from_flow_obj(
        cls, flow: "prefect.Flow", allow_archived: bool = False
    ) -> "FlowView":
        """
        Get an instance of this class given a `flow` object. Lookups are done by
        searching for matches using the serialized flow

        Args:
            flow: The flow object to use
            allow_archived: By default, archived flows are not included in the query
                because it is possible that more than one flow will be found. If `True`
                an archived flow can be returned.

        Returns:
            A new instance of FlowView
        """
        where: Dict[str, Any] = {
            "serialized_flow": {"_eq": EnumValue("$serialized_flow")},
        }
        if not allow_archived:
            where["archived"] = {"_eq": False}

        return cls.from_flow_data(
            cls.query_for_flow(
                where=where,
                jsonb_variables={"serialized_flow": flow.serialize()},
            )
        )

    @classmethod
    def from_flow_name(
        cls, flow_name: str, project_name: str = "", last_updated: bool = False
    ) -> "FlowView":
        """
        Get an instance of this class given a flow name. Optionally, a project name can
        be included since flow names are not guaranteed to be unique across projects.

        Args:
            flow_name: The name of the flow to lookup
            project_name: The name of the project to lookup. If `None`, flows with an
                explicitly null project will be searched. If `""` (default), the
                lookup will be across all projects.
            last_updated: By default, if multiple flows are found an error will be
                thrown. If `True`, the most recently updated flow will be returned
                instead.

        Returns:
            A new instance of FlowView
        """
        where: Dict[str, Any] = {"name": {"_eq": flow_name}, "archived": {"_eq": False}}
        if project_name != "":
            where["project"] = {
                "name": ({"_eq": project_name} if project_name else {"_is_null": True})
            }

        flows = cls.query_for_flow(
            where=where,
            order_by={"updated_at": EnumValue("desc")},
        )
        if len(flows) > 1 and not last_updated:
            raise ValueError(
                f"Found multiple flows matching {where}. "
                "Provide a `project_name` as well or toggle `last_updated` "
                "to use the flow that was most recently updated"
            )

        flow = flows[0]
        return cls.from_flow_data(flow)

    @staticmethod
    def query_for_flow(where: dict, **kwargs: Any) -> dict:
        """
        Query for flow data using `query_for_flows` but throw an exception if
        more than one matching flow is found

        Args:
            where: The `where` clause to use
            **kwargs: Additional kwargs are passed to `query_for_flows`

        Returns:
            A dict of flow data
        """
        flows = FlowView.query_for_flows(where=where, **kwargs)

        if len(flows) > 1:
            raise ValueError(
                f"Found multiple ({len(flows)}) flows while querying for flows "
                f"where {where}: {flows}"
            )

        if not flows:
            return {}

        flow = flows[0]
        return flow

    @staticmethod
    def query_for_flows(
        where: dict,
        order_by: dict = None,
        error_on_empty: bool = True,
        jsonb_variables: Dict[str, dict] = None,
    ) -> List[dict]:
        """
        Query for task run data necessary to initialize `Flow` instances
        with `Flow.from_flow_data`.

        Args:
            where (required): The Hasura `where` clause to filter by
            order_by (optional): An optional Hasura `order_by` clause to order results
                by
            error_on_empty (optional): If `True` and no tasks are found, a `ValueError`
                will be raised
            jsonb_variables (optional): Dict-typed variables to inject into the query
                as jsonb GraphQL types. Keys must be consumed in the query i.e.
                in the passed `where` clause as `EnumValue("$key")`


        Only `jsonb` variables are exposed because GraphQL queries will fail with where
        clauses containing jsonb directly but succeed when they are a sent as query
        variables because they are unescaped.

        Returns:
            A dict of task run information (or a list of dicts if `many` is `True`)
        """
        client = prefect.Client()

        query_args = {"where": where}
        if order_by is not None:
            query_args["order_by"] = order_by

        jsonb_variables = jsonb_variables or {}
        variable_declarations = ""
        if jsonb_variables:
            # Validate the variable types
            for key, val in jsonb_variables.items():
                if not isinstance(val, dict):
                    raise ValueError(
                        f"Passed variable {key!r} is of type {type(val).__name__}, "
                        "expected 'dict'. Other types are not supported."
                    )
            # Generate a list of variable declarations
            variable_types = ", ".join(
                [f"${key}: jsonb" for key in jsonb_variables.keys()]
            )
            variable_declarations = f"({variable_types})"

        flow_query = {
            f"query{variable_declarations}": {
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
                    "flow_group_id": True,
                }
            }
        }

        result = client.graphql(flow_query, variables=jsonb_variables)
        flows = result.get("data", {}).get("flow", None)

        if flows is None:
            raise ValueError(
                f"Received bad result while querying for flows where {where}: "
                f"{result}"
            )

        if not flows:  # Empty list
            if error_on_empty:
                raise ValueError(
                    f"No results found while querying for flows where {where!r}"
                )
            return []

        # Return a list
        return flows

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}"
            "("
            + ", ".join(
                [
                    f"flow_id={self.flow_id!r}",
                    f"name={self.name!r}",
                    f"project_name={self.project_name!r}"
                    f"storage_type={type(self.storage).__name__}",
                ]
            )
            + ")"
        )
