from typing import Any, Dict, List
from prefect.tasks.monte_carlo.client import MonteCarloClient

import prefect
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class MonteCarloIncorrectTagsFormat(Exception):
    """Exception for incorrect tags format"""

    pass


class MonteCarloCreateOrUpdateLineage(Task):
    """
    Task for creating or updating a lineage node for the given source and destination nodes,
    as well as for creating a lineage edge between those nodes.

    Args:
        - source (dict, optional): a source node configuration. Expected to include the following
            keys: `node_name`, `object_id`, `object_type`, `resource_name`, and optionally also
            a list of `tags`.
        - destination (dict, optional): a destination node configuration. Expected to include
            the following keys: `node_name`, `object_id`, `object_type`, `resource_name`,
            and optionally also a list of `tags`.
        - api_key_id (string, optional): to use this task,
            you need to pass the Monte Carlo API credentials.
            Those can be created using https://getmontecarlo.com/settings/api.
            To avoid passing the credentials
            in plain text, you can leverage the PrefectSecret task in your flow.
        - api_token (string, optional): the API token.
             To avoid passing the credentials in plain text,
             you can leverage PrefectSecret task in your flow.
        - prefect_context_tags (bool, optional): whether to automatically add
            tags with Prefect context.
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
            tags=[{"propertyName": "prefect_test_key", "propertyValue": "prefect_test_value"}]
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
            tags=[{"propertyName": "prefect_test_key", "propertyValue": "prefect_test_value"}]
        )
        ```

    """

    catalog_url = "https://getmontecarlo.com/catalog"

    def __init__(
        self,
        source: Dict[str, str] = None,
        destination: Dict[str, str] = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tags: bool = True,
        expire_at: str = None,
        **kwargs: Any,
    ):
        self.source = source
        self.destination = destination
        self.api_key_id = api_key_id
        self.api_token = api_token
        self.prefect_context_tags = prefect_context_tags
        self.expire_at = expire_at
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "source",
        "destination",
        "api_key_id",
        "api_token",
        "prefect_context_tags",
        "expire_at",
    )
    def run(
        self,
        source: Dict[str, Any] = None,
        destination: Dict[str, Any] = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tags: bool = True,
        expire_at: str = None,
    ) -> Dict[str, Any]:
        """
        Creates or updates a lineage node for the given source and destination,
        and creates a lineage edge between them.
        If a list of `tags` is set for either source or destination (or both),
        the task adds those to the source and/or destination nodes.
        If no `tags` are set, the task
        creates a node without custom tags. Additionally,
        if the `prefect_context_tags` flag is set to True (default),
        the task creates tags with information from Prefect context
        for debugging data downtime issues.

        Args:
            - source (dict, optional): a source node configuration.
                Expected to include the following keys: `node_name`,
                `object_id`, `object_type`, `resource_name`, and optionally also
                a list of `tags`.
            - destination (dict, optional): a destination node configuration.
                Expected to include the following keys:
                `node_name`, `object_id`, `object_type`, `resource_name`,
                and optionally also a list of `tags`.
            - api_key_id (string, optional): to use this task, you need to pass
                the Monte Carlo API credentials.
                Those can be created using https://getmontecarlo.com/settings/api.
                To avoid passing the credentials
                in plain text, you can leverage the PrefectSecret task in your flow.
            - api_token (string, optional): the API token.
                 To avoid passing the credentials in plain text,
                 you can leverage PrefectSecret task in your flow.
            - prefect_context_tags (bool, optional): whether to automatically add
                tags with Prefect context.
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

        # source node
        if source.get("tags") is None and prefect_context_tags is False:
            source_node_mcon = mc.create_or_update_lineage_node(
                source["node_name"],
                source["object_id"],
                source["object_type"],
                source["resource_name"],
            )
        elif source.get("tags") is None and prefect_context_tags is True:
            source_node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                source["node_name"],
                source["object_id"],
                source["object_type"],
                source["resource_name"],
                tags=get_prefect_context_tags(),
            )
        elif source.get("tags") is not None and prefect_context_tags is False:
            source_node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                source["node_name"],
                source["object_id"],
                source["object_type"],
                source["resource_name"],
                source["tags"],
            )
        else:
            lineage_tags = [*source["tags"], *get_prefect_context_tags()]
            source_node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                source["node_name"],
                source["object_id"],
                source["object_type"],
                source["resource_name"],
                lineage_tags,
            )
        source_node_url = f"{self.catalog_url}/{source_node_mcon}/table"
        self.logger.info("Created or updated a source lineage node %s", source_node_url)

        # destination node
        if destination.get("tags") is None and prefect_context_tags is False:
            destination_node_mcon = mc.create_or_update_lineage_node(
                destination["node_name"],
                destination["object_id"],
                destination["object_type"],
                destination["resource_name"],
            )
        elif destination.get("tags") is None and prefect_context_tags is True:
            destination_node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                destination["node_name"],
                destination["object_id"],
                destination["object_type"],
                destination["resource_name"],
                tags=get_prefect_context_tags(),
            )
        elif destination.get("tags") is not None and prefect_context_tags is False:
            destination_node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                destination["node_name"],
                destination["object_id"],
                destination["object_type"],
                destination["resource_name"],
                destination["tags"],
            )
        else:
            lineage_tags = [*destination["tags"], *get_prefect_context_tags()]
            destination_node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                destination["node_name"],
                destination["object_id"],
                destination["object_type"],
                destination["resource_name"],
                lineage_tags,
            )
        destination_node_url = f"{self.catalog_url}/{destination_node_mcon}/table"
        self.logger.info(
            "Created or updated a destination lineage node %s", destination_node_url
        )

        # edge between source and destination nodes
        edge_id = mc.create_or_update_lineage_edge(source, destination, expire_at)
        self.logger.info("Created or updated a destination lineage edge %s", edge_id)
        return edge_id


class MonteCarloCreateOrUpdateNodeWithTags(Task):
    """
    Task for creating or updating a lineage node in the Monte Carlo Catalog
    and enriching it with multiple metadata tags.
    If the `prefect_context_tags` flag is set to True (default),
    the task additionally creates tags with Prefect
    context for debugging data downtime issues.

    Args:
        - node_name (string, optional): the display name of a lineage node.
        - object_id (string, optional): the object ID of a lineage node.
        - object_type (string, optional): the object type of a lineage node - usually,
            either "table" or "view".
        - resource_name (string, optional): name of the data warehouse or custom resource.
            All resources can be retrieved via a separate task.
        - lineage_tags (list, optional): a list of dictionaries where each dictionary is a single tag.
        - api_key_id (string, optional): to use this task, you need to pass
            the Monte Carlo API credentials.
            Those can be created using https://getmontecarlo.com/settings/api.
            To avoid passing the credentials
            in plain text, you can leverage the PrefectSecret task in your flow.
        - api_token (string, optional): the API token.
             To avoid passing the credentials in plain text,
             you can leverage the PrefectSecret task in your flow.
        - prefect_context_tags (bool, optional): whether to automatically add
            tags with Prefect context.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor.

        The expected format for `lineage_tags`:

        ```python
        [{"propertyName": "tag_name", "propertyValue": "your_tag_value"},
        {"propertyName": "another_tag_name", "propertyValue": "your_tag_value"}]
        ```
    """

    def __init__(
        self,
        node_name: str = None,
        object_id: str = None,
        object_type: str = None,
        resource_name: str = None,
        lineage_tags: List[Dict[str, str]] = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tags: bool = True,
        **kwargs: Any,
    ):
        self.node_name = node_name
        self.object_id = object_id
        self.object_type = object_type
        self.resource_name = resource_name
        self.lineage_tags = lineage_tags
        self.api_key_id = api_key_id
        self.api_token = api_token
        self.prefect_context_tags = prefect_context_tags
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "node_name",
        "object_id",
        "object_type",
        "resource_name",
        "lineage_tags",
        "api_key_id",
        "api_token",
        "prefect_context_tags",
    )
    def run(
        self,
        node_name: str = None,
        object_id: str = None,
        object_type: str = None,
        resource_name: str = None,
        lineage_tags: List[Dict[str, str]] = None,
        api_key_id: str = None,
        api_token: str = None,
        prefect_context_tags: bool = True,
    ) -> str:
        """
        Creates or updates multiple metadata tags for a given lineage node in the Monte Carlo Catalog.
        If the `prefect_context_tags` flag is set to True (default), the task additionally creates
        a tag with the Prefect context dictionary for debugging data downtime issues.

        Args:
            - node_name (string, optional): the display name of a lineage node.
            - object_id (string, optional): the object ID of a lineage node.
            - object_type (string, optional): the object type of a lineage node - usually,
                either "table" or "view".
            - resource_name (string, optional): name of the data warehouse or custom resource.
                All resources can be retrieved via a separate task.
            - lineage_tags (list, optional): a list of dictionaries
                where each dictionary is a single tag.
            - api_key_id (string, optional): to use this task,
                you need to pass the Monte Carlo API credentials.
                Those can be created using https://getmontecarlo.com/settings/api.
                To avoid passing the credentials
                in plain text, you can leverage the PrefectSecret task in your flow.
            - api_token (string, optional): the API token.
                 To avoid passing the credentials in plain text,
                 you can leverage the PrefectSecret task in your flow.
            - prefect_context_tags (bool, optional): whether to automatically add a tag
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
        if api_key_id is None:
            raise ValueError("Value for `api_key_id` must be provided.")
        if api_token is None:
            raise ValueError("Value for `api_token` must be provided.")

        mc = MonteCarloClient(api_key_id, api_token)
        if lineage_tags is None and prefect_context_tags is False:
            node_mcon = mc.create_or_update_lineage_node(
                node_name,
                object_id,
                object_type,
                resource_name,
            )
        else:
            for tag in lineage_tags:
                if sorted(tag.keys()) != ["propertyName", "propertyValue"]:
                    raise MonteCarloIncorrectTagsFormat(
                        "Must provide tags in the format "
                        '[{"propertyName": "tag_name", "propertyValue": "tag_value"}].',
                        "You provided: ",
                        tag,
                    )
            if prefect_context_tags is False:
                node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                    node_name,
                    object_id,
                    object_type,
                    resource_name,
                    lineage_tags,
                )
            else:
                final_tags = [*lineage_tags, *get_prefect_context_tags()]
                node_mcon = mc.create_or_update_lineage_node_with_multiple_tags(
                    node_name, object_id, object_type, resource_name, tags=final_tags
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


def get_prefect_context_tags() -> List[Dict[str, Any]]:
    """
    Helper function to generate a list of Prefect context tags
    when `prefect_context_tags` is set to True.

    Returns:
        - list: a list of dictionaries with the task's context.
    """
    return [
        dict(propertyName="flow_id", propertyValue=str(prefect.context.get("flow_id"))),
        dict(
            propertyName="flow_name",
            propertyValue=str(prefect.context.get("flow_name")),
        ),
        dict(
            propertyName="flow_run_id",
            propertyValue=str(prefect.context.get("flow_run_id")),
        ),
        dict(
            propertyName="flow_run_name",
            propertyValue=str(prefect.context.get("flow_run_name")),
        ),
        dict(
            propertyName="flow_run_version",
            propertyValue=str(prefect.context.get("flow_run_version")),
        ),
        dict(
            propertyName="project_id",
            propertyValue=str(prefect.context.get("project_id")),
        ),
        dict(
            propertyName="project_name",
            propertyValue=str(prefect.context.get("project_name")),
        ),
        dict(
            propertyName="scheduled_start_time",
            propertyValue=str(prefect.context.get("scheduled_start_time")),
        ),
        dict(
            propertyName="execution_start_time",
            propertyValue=str(prefect.context.get("date")),
        ),
        dict(propertyName="task_id", propertyValue=str(prefect.context.get("task_id"))),
        dict(
            propertyName="task_run_id",
            propertyValue=str(prefect.context.get("task_run_id")),
        ),
        dict(
            propertyName="task_run_name",
            propertyValue=str(prefect.context.get("task_run_name")),
        ),
        dict(
            propertyName="task_slug",
            propertyValue=str(prefect.context.get("task_slug")),
        ),
        dict(
            propertyName="task_name",
            propertyValue=str(prefect.context.get("task_name")),
        ),
        dict(
            propertyName="task_full_name",
            propertyValue=str(prefect.context.get("task_full_name")),
        ),
        dict(
            propertyName="task_run_count",
            propertyValue=str(prefect.context.get("task_run_count")),
        ),
        dict(
            propertyName="map_index",
            propertyValue=str(prefect.context.get("map_index")),
        ),
        dict(
            propertyName="parameters",
            propertyValue=str(prefect.context.get("parameters")),
        ),
        dict(
            propertyName="running_with_backend",
            propertyValue=str(prefect.context.get("running_with_backend")),
        ),
    ]
