import json
from typing import Any, Dict, List
from prefect.tasks.monte_carlo.client import MonteCarloClient

import prefect
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class MonteCarloCreateOrUpdateLineage(Task):
    """
    Task for creating or updating a lineage node for the given source and destination nodes,
    as well as for creating a lineage edge between those nodes.

    Args:
        - source (dict, optional): a source node configuration. Expected to include the following
        keys: `node_name`, `object_id`, `object_type`, `resource_name`, and optionally also
        `metadata_key` and `metadata_value`.
        - destination (dict, optional): a destination node configuration. Expected to include
        the following keys: `node_name`, `object_id`, `object_type`, `resource_name`,
        and optionally also `metadata_key` and `metadata_value`.
        - api_key_id (string, optional): to use this task,
        you need to pass the Monte Carlo API credentials.
        Those can be created using https://getmontecarlo.com/settings/api.
        To avoid passing the credentials
        in plain text, you can leverage the PrefectSecret task in your flow.
        - api_token (string, optional): the API token.
         To avoid passing the credentials in plain text,
         you can leverage PrefectSecret task in your flow.
        - prefect_context_tag (bool, optional): whether to automatically add
        a tag with Prefect context.
        - expire_at (string, optional): date and time indicating when to expire
        a source-destination edge. You can expire specific lineage nodes.
        If this value is set, the
        edge between a source and destination nodes will expire on a given date.
        Expected format: "YYYY-MM-DDTHH:mm:ss.SSS". For example, "2042-01-01T00:00:00.000".
        - **kwargs (dict, optional): additional keyword arguments to pass
        to the Task constructor.

        Example source:

        ```python
        source = dict(
            # this may be a shorter version of object_id
            node_name="example_table_name",
            object_id="example_table_name",
            # "table" is recommended, but you can use any string, e.g. "csv_file"
            object_type="table",
            resource_name="name_your_source_system",
            metadata_key="your_key_name",
            metadata_value="your_abitrary_value",
        )
        ```

        Example destination:

        ```python
        destination = dict(
            # the full name of a data warehouse table
            node_name="db_name:schema_name.table_name",
            object_id="db_name:schema_name.table_name",
            # "table" is recommended, but you can use any string, e.g. "csv_file"
            object_type="table",
            resource_name="your_dwh_resource_name",
            metadata_key="your_optional_key_name",
            metadata_value="your_optional_abitrary_value",
        )
        ```

    """

    def __init__(
        self,
        source: Dict[str, str] = None,
        destination: Dict[str, str] = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tag: bool = True,
        expire_at: str = None,
        **kwargs: Any,
    ):
        self.source = source
        self.destination = destination
        self.api_key_id = api_key_id
        self.api_token = api_token
        self.prefect_context_tag = prefect_context_tag
        self.expire_at = expire_at
        self._catalog_url = "https://getmontecarlo.com/catalog"
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source",
        "destination",
        "api_key_id",
        "api_token",
        "prefect_context_tag",
        "expire_at",
    )
    def run(
        self,
        source: Dict[str, str] = None,
        destination: Dict[str, str] = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tag: bool = True,
        expire_at: str = None,
    ) -> Dict[str, Any]:
        """
        Creates or updates a lineage node for the given source and destination,
        and creates a lineage edge between them.
        If the `metadata_key` and `metadata_value` are set for either source or destination (or both),
        the task adds those as tags to the source and/or destination nodes.
        If no key-value pair is set, the task
        creates a node without custom tags. Additionally,
        if the `prefect_context_tag` flag is set to True (default),
        the task creates a tag with the Prefect context dictionary for debugging data downtime issues.

        Args:
            - source (dict, optional): a source node configuration.
            Expected to include the following keys: `node_name`,
            `object_id`, `object_type`, `resource_name`, and optionally also
            `metadata_key` and `metadata_value`.
            - destination (dict, optional): a destination node configuration.
            Expected to include the following keys:
            `node_name`, `object_id`, `object_type`, `resource_name`,
            and optionally also `metadata_key` and `metadata_value`.
            - api_key_id (string, optional): to use this task, you need to pass
            the Monte Carlo API credentials.
            Those can be created using https://getmontecarlo.com/settings/api.
            To avoid passing the credentials
            in plain text, you can leverage the PrefectSecret task in your flow.
            - api_token (string, optional): the API token.
             To avoid passing the credentials in plain text,
             you can leverage PrefectSecret task in your flow.
            - prefect_context_tag (bool, optional): whether to automatically add
            a tag with Prefect context.
            - expire_at (string, optional): date and time indicating when to expire
            a source-destination edge. You can expire specific lineage nodes.
            If this value is set, the
            edge between a source and destination nodes will expire on a given date.
            Expected format: "YYYY-MM-DDTHH:mm:ss.SSS". For example, "2042-01-01T00:00:00.000".

        Returns:
            - dict: a GraphQL response dictionary with the edge ID.
        """
        if api_key_id is None:
            raise ValueError("Value for `api_key_id` must be provided.")

        if api_token is None:
            raise ValueError("Value for `api_token` must be provided.")

        if source.get("node_name") is None or destination.get("node_name") is None:
            raise ValueError(
                "Must provide a `node_name` in both source and destination."
            )

        if source.get("object_id") is None or destination.get("object_id") is None:
            raise ValueError(
                "Must provide an `object_id` in both source and destination."
            )

        if source.get("object_type") is None:
            source["object_type"] = "table"

        if destination.get("object_type") is None:
            destination["object_type"] = "table"

        if (
            source.get("resource_name") is None
            or destination.get("resource_name") is None
        ):
            raise ValueError(
                "Must provide a `resource_name` in both source and destination."
            )

        mc = MonteCarloClient(api_key_id, api_token)
        if source.get("metadata_key") is None or source.get("metadata_value") is None:
            source_node_mcon = mc.create_or_update_lineage_node(
                source["node_name"],
                source["object_id"],
                source["object_type"],
                source["resource_name"],
            )
        else:
            source_node_mcon = mc.create_or_update_lineage_node_with_tag(
                source["node_name"],
                source["object_id"],
                source["object_type"],
                source["resource_name"],
                source["metadata_key"],
                source["metadata_value"],
            )
        source_node_url = f"{self._catalog_url}/{source_node_mcon}/table"
        self.logger.info("Created or updated a source lineage node %s", source_node_url)

        if (
            destination.get("metadata_key") is None
            or destination.get("metadata_value") is None
        ):
            destination_node_mcon = mc.create_or_update_lineage_node(
                destination["node_name"],
                destination["object_id"],
                destination["object_type"],
                destination["resource_name"],
            )
        else:
            destination_node_mcon = mc.create_or_update_lineage_node_with_tag(
                destination["node_name"],
                destination["object_id"],
                destination["object_type"],
                destination["resource_name"],
                destination["metadata_key"],
                destination["metadata_value"],
            )
        destination_node_url = f"{self._catalog_url}/{destination_node_mcon}/table"
        self.logger.info(
            "Created or updated a destination lineage node %s", destination_node_url
        )

        response = mc.create_or_update_lineage_edge(source, destination, expire_at)
        self.logger.debug("Lineage edge response: %s", response)
        if prefect_context_tag:
            self.logger.info("Setting Prefect context tags on the lineage nodes...")
            mc.create_or_update_tags_for_mcon(
                mcon=source_node_mcon,
                key="prefect_context",
                value=get_prefect_context(),
            )
            mc.create_or_update_tags_for_mcon(
                mcon=destination_node_mcon,
                key="prefect_context",
                value=get_prefect_context(),
            )
        return response


class MonteCarloCreateOrUpdateNodeWithTag(Task):
    """
    Task for creating or updating a lineage node in the Monte Carlo Catalog
    and enriching it with metadata tags.
    If the `prefect_context_tag` flag is set to True (default),
    the task additionally creates a tag with the Prefect
    context dictionary for debugging data downtime issues.

    Args:
        - node_name (string, optional): the display name of a lineage node.
        - object_id (string, optional): the object ID of a lineage node.
        - object_type (string, optional): the object type of a lineage node - usually,
        either "table" or "view".
        - resource_name (string, optional): name of the data warehouse or custom resource.
        All resources can be retrieved via a separate task.
        - metadata_key (string, optional): the metadata tag name.
        - metadata_value (string, optional): the value of a metadata tag.
        - api_key_id (string, optional): to use this task, you need to pass
        the Monte Carlo API credentials.
        Those can be created using https://getmontecarlo.com/settings/api.
        To avoid passing the credentials
        in plain text, you can leverage the PrefectSecret task in your flow.
        - api_token (string, optional): the API token.
         To avoid passing the credentials in plain text,
         you can leverage the PrefectSecret task in your flow.
        - prefect_context_tag (bool, optional): whether to automatically add
        a tag with Prefect context.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor.
    """

    def __init__(
        self,
        node_name: str = None,
        object_id: str = None,
        object_type: str = None,
        resource_name: str = None,
        metadata_key: str = None,
        metadata_value: str = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tag: bool = True,
        **kwargs: Any,
    ):
        self.node_name = node_name
        self.object_id = object_id
        self.object_type = object_type
        self.resource_name = resource_name
        self.metadata_key = metadata_key
        self.metadata_value = metadata_value
        self.api_key_id = api_key_id
        self.api_token = api_token
        self.prefect_context_tag = prefect_context_tag
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "node_name",
        "object_id",
        "object_type",
        "resource_name",
        "metadata_key",
        "metadata_value",
        "api_key_id",
        "api_token",
        "prefect_context_tag",
    )
    def run(
        self,
        node_name: str = None,
        object_id: str = None,
        object_type: str = None,
        resource_name: str = None,
        metadata_key: str = None,
        metadata_value: str = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tag: bool = True,
    ) -> str:
        """
        Creates or updates metadata tags for a given lineage node in the Monte Carlo Catalog.
        If the `prefect_context_tag` flag is set to True (default), the task additionally creates
        a tag with the Prefect context dictionary for debugging data downtime issues.

        Args:
            - node_name (string, optional): the display name of a lineage node.
            - object_id (string, optional): the object ID of a lineage node.
            - object_type (string, optional): the object type of a lineage node - usually,
            either "table" or "view".
            - resource_name (string, optional): name of the data warehouse or custom resource.
            All resources can be retrieved via a separate task.
            - metadata_key (string, optional): the metadata tag name.
            - metadata_value (string, optional): the value of a metadata tag.
            - api_key_id (string, optional): to use this task,
            you need to pass the Monte Carlo API credentials.
            Those can be created using https://getmontecarlo.com/settings/api.
            To avoid passing the credentials
            in plain text, you can leverage the PrefectSecret task in your flow.
            - api_token (string, optional): the API token.
             To avoid passing the credentials in plain text,
             you can leverage the PrefectSecret task in your flow.
            - prefect_context_tag (bool, optional): whether to automatically add a tag
            with Prefect context.

        Returns:
            - string: MCON - a Monte Carlo internal ID of the node.
        """
        if node_name is None:
            raise ValueError("Value for `node_name` must be provided.")
        if object_id is None:
            raise ValueError("Value for `object_id` must be provided.")
        if object_type is None:
            raise ValueError("Value for `object_type` must be provided.")
        if resource_name is None:
            raise ValueError("Value for `resource_name` must be provided.")
        if metadata_key is None:
            raise ValueError("Value for `metadata_key` must be provided.")
        if metadata_value is None:
            raise ValueError("Value for `metadata_value` must be provided.")
        if api_key_id is None:
            raise ValueError("Value for `api_key_id` must be provided.")
        if api_token is None:
            raise ValueError("Value for `api_token` must be provided.")

        mc = MonteCarloClient(api_key_id, api_token)
        node_mcon = mc.create_or_update_lineage_node_with_tag(
            node_name,
            object_id,
            object_type,
            resource_name,
            metadata_key,
            metadata_value,
        )
        if prefect_context_tag:
            self.logger.info("Setting Prefect context tags on the lineage nodes...")
            mc.create_or_update_tags_for_mcon(
                mcon=node_mcon, key="prefect_context", value=get_prefect_context()
            )
        return node_mcon


class MonteCarloGetResources(Task):
    """
    Task for querying resources using the Monte Carlo API.
    You can use this task to find the
    name of your data warehouse or other resource, and use it as `resource_name`
    in other Monte Carlo tasks.

    Args:
        - api_key_id (string, optional): to use this task, you need to pass
        the Monte Carlo API credentials.
        Those can be created using https://getmontecarlo.com/settings/api.
        To avoid passing the credentials
        in plain text, you can leverage the PrefectSecret task in your flow.
        - api_token (string, optional): the API token.
         To avoid passing the credentials in plain text, you can leverage the PrefectSecret task
         in your flow.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
        Task constructor.
    """

    def __init__(
        self,
        api_key_id: str = None,
        api_token: str = None,
        **kwargs: Any,
    ):
        self.api_key_id = api_key_id
        self.api_token = api_token
        super().__init__(**kwargs)

    @defaults_from_attrs("api_key_id", "api_token")
    def run(
        self,
        api_key_id: str = None,
        api_token: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all Monte Carlo resources.

        Args:
            - api_key_id (string, optional): to use this task,
            you need to pass the Monte Carlo API credentials.
            Those can be created using https://getmontecarlo.com/settings/api.
            To avoid passing the credentials
            in plain text, you can leverage the PrefectSecret task in your flow.
            - api_token (string, optional): the API token.
             To avoid passing the credentials in plain text, you can leverage the PrefectSecret
             task in your flow.

        Returns:
            - list: Monte Carlo resources, including all existing data warehouses and custom resources.
        """
        if api_key_id is None:
            raise ValueError("Value for `api_key_id` must be provided.")
        if api_token is None:
            raise ValueError("Value for `api_token` must be provided.")
        mc = MonteCarloClient(api_key_id, api_token)
        return mc.get_resources()


def get_prefect_context() -> str:
    """
    Helper function used to generate Prefect context tag
    when `prefect_context_tag` is set to True.
    Returns:
        - string: a JSON string with the task's context.
    """
    return json.dumps(
        dict(
            flow_id=prefect.context.get("flow_id"),
            flow_name=prefect.context.get("flow_name"),
            flow_run_id=prefect.context.get("flow_run_id"),
            flow_run_name=prefect.context.get("flow_run_name"),
            flow_run_version=prefect.context.get("flow_run_version"),
            project_id=prefect.context.get("project_id"),
            project_name=prefect.context.get("project_name"),
            scheduled_start_time=str(prefect.context.get("scheduled_start_time")),
            execution_start_time=str(prefect.context.get("date")),
            task_id=prefect.context.get("task_id"),
            task_run_id=prefect.context.get("task_run_id"),
            task_run_name=prefect.context.get("task_run_name"),
            task_slug=prefect.context.get("task_slug"),
            task_name=prefect.context.get("task_name"),
            task_full_name=prefect.context.get("task_full_name"),
            task_run_count=prefect.context.get("task_run_count"),
            map_index=prefect.context.get("map_index"),
            parameters=prefect.context.get("parameters"),
            running_with_backend=prefect.context.get("running_with_backend"),
        ),
        indent=4,
        sort_keys=True,
        default=str,
    )
