---
sidebarDepth: 2
editLink: false
---
# Monte Carlo Tasks

!!! tip Verified by Prefect
<div class="verified-task">
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48" fill="none">
<circle cx="24" cy="24" r="24" fill="#42b983"/>
<circle cx="24" cy="24" r="9" stroke="#fff" stroke-width="2"/>
<path d="M19 24L22.4375 27L29 20.5" stroke="#fff" stroke-width="2"/>
</svg>
<div>
    These tasks have been tested and verified by Prefect.
</div>
</div>

---

 ## MonteCarloCreateOrUpdateLineage
 <div class='class-sig' id='prefect-tasks-monte-carlo-monte-carlo-lineage-montecarlocreateorupdatelineage'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.monte_carlo.monte_carlo_lineage.MonteCarloCreateOrUpdateLineage</p>(source=None, destination=None, api_key_id=None, api_token=None, prefect_context_tags=True, expire_at=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monte_carlo/monte_carlo_lineage.py#L15">[source]</a></span></div>

Task for creating or updating a lineage node for the given source and destination nodes, as well as for creating a lineage edge between those nodes.

**Args**:     <ul class="args"><li class="args">`source (dict, optional)`: a source node configuration. Expected to include the following         keys: `node_name`, `object_id`, `object_type`, `resource_name`, and optionally also         a list of `tags`.     </li><li class="args">`destination (dict, optional)`: a destination node configuration. Expected to include         the following keys: `node_name`, `object_id`, `object_type`, `resource_name`,         and optionally also a list of `tags`.     </li><li class="args">`api_key_id (string, optional)`: to use this task,         you need to pass the Monte Carlo API credentials.         Those can be created using https://getmontecarlo.com/settings/api.         To avoid passing the credentials         in plain text, you can leverage the PrefectSecret task in your flow.     </li><li class="args">`api_token (string, optional)`: the API token.          To avoid passing the credentials in plain text,          you can leverage PrefectSecret task in your flow.     </li><li class="args">`prefect_context_tags (bool, optional)`: whether to automatically add         tags with Prefect context.     </li><li class="args">`expire_at (string, optional)`: date and time indicating when to expire         a source-destination edge. You can expire specific lineage nodes.         If this value is set, the         edge between a source and destination nodes will expire on a given date.         Expected format: "YYYY-MM-DDTHH:mm:ss.SSS". For example, "2042-01-01T00:00:00.000".     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass         to the Task constructor.</li></ul>     Example source:


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

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-monte-carlo-monte-carlo-lineage-montecarlocreateorupdatelineage-run'><p class="prefect-class">prefect.tasks.monte_carlo.monte_carlo_lineage.MonteCarloCreateOrUpdateLineage.run</p>(source=None, destination=None, api_key_id=None, api_token=None, prefect_context_tags=True, expire_at=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monte_carlo/monte_carlo_lineage.py#L95">[source]</a></span></div>
<p class="methods">Creates or updates a lineage node for the given source and destination, and creates a lineage edge between them. If a list of `tags` is set for either source or destination (or both), the task adds those to the source and/or destination nodes. If no `tags` are set, the task creates a node without custom tags. Additionally, if the `prefect_context_tags` flag is set to True (default), the task creates tags with information from Prefect context for debugging data downtime issues.<br><br>**Args**:     <ul class="args"><li class="args">`source (dict, optional)`: a source node configuration.         Expected to include the following keys: `node_name`,         `object_id`, `object_type`, `resource_name`, and optionally also         a list of `tags`.     </li><li class="args">`destination (dict, optional)`: a destination node configuration.         Expected to include the following keys:         `node_name`, `object_id`, `object_type`, `resource_name`,         and optionally also a list of `tags`.     </li><li class="args">`api_key_id (string, optional)`: to use this task, you need to pass         the Monte Carlo API credentials.         Those can be created using https://getmontecarlo.com/settings/api.         To avoid passing the credentials         in plain text, you can leverage the PrefectSecret task in your flow.     </li><li class="args">`api_token (string, optional)`: the API token.          To avoid passing the credentials in plain text,          you can leverage PrefectSecret task in your flow.     </li><li class="args">`prefect_context_tags (bool, optional)`: whether to automatically add         tags with Prefect context.     </li><li class="args">`expire_at (string, optional)`: date and time indicating when to expire         a source-destination edge. You can expire specific lineage nodes.         If this value is set, the         edge between a source and destination nodes will expire on a given date.         Expected format: "YYYY-MM-DDTHH:mm:ss.SSS". For example, "2042-01-01T00:00:00.000".</li></ul> **Returns**:     <ul class="args"><li class="args">`dict`: a GraphQL response dictionary with the edge ID.</li></ul></p>|

---
<br>

 ## MonteCarloCreateOrUpdateNodeWithTags
 <div class='class-sig' id='prefect-tasks-monte-carlo-monte-carlo-lineage-montecarlocreateorupdatenodewithtags'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.monte_carlo.monte_carlo_lineage.MonteCarloCreateOrUpdateNodeWithTags</p>(node_name=None, object_id=None, object_type=None, resource_name=None, lineage_tags=None, api_key_id=None, api_token=None, prefect_context_tags=True, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monte_carlo/monte_carlo_lineage.py#L263">[source]</a></span></div>

Task for creating or updating a lineage node in the Monte Carlo Catalog and enriching it with multiple metadata tags. If the `prefect_context_tags` flag is set to True (default), the task additionally creates tags with Prefect context for debugging data downtime issues.

**Args**:     <ul class="args"><li class="args">`node_name (string, optional)`: the display name of a lineage node.     </li><li class="args">`object_id (string, optional)`: the object ID of a lineage node.     </li><li class="args">`object_type (string, optional)`: the object type of a lineage node - usually,         either "table" or "view".     </li><li class="args">`resource_name (string, optional)`: name of the data warehouse or custom resource.         All resources can be retrieved via a separate task.     </li><li class="args">`lineage_tags (list, optional)`: a list of dictionaries where each dictionary is a single tag.     </li><li class="args">`api_key_id (string, optional)`: to use this task, you need to pass         the Monte Carlo API credentials.         Those can be created using https://getmontecarlo.com/settings/api.         To avoid passing the credentials         in plain text, you can leverage the PrefectSecret task in your flow.     </li><li class="args">`api_token (string, optional)`: the API token.          To avoid passing the credentials in plain text,          you can leverage the PrefectSecret task in your flow.     </li><li class="args">`prefect_context_tags (bool, optional)`: whether to automatically add         tags with Prefect context.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the Task constructor.</li></ul>     The expected format for `lineage_tags`:


```python
    [{"propertyName": "tag_name", "propertyValue": "your_tag_value"},
    {"propertyName": "another_tag_name", "propertyValue": "your_tag_value"}]

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-monte-carlo-monte-carlo-lineage-montecarlocreateorupdatenodewithtags-run'><p class="prefect-class">prefect.tasks.monte_carlo.monte_carlo_lineage.MonteCarloCreateOrUpdateNodeWithTags.run</p>(node_name=None, object_id=None, object_type=None, resource_name=None, lineage_tags=None, api_key_id=None, api_token=None, prefect_context_tags=True)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monte_carlo/monte_carlo_lineage.py#L321">[source]</a></span></div>
<p class="methods">Creates or updates multiple metadata tags for a given lineage node in the Monte Carlo Catalog. If the `prefect_context_tags` flag is set to True (default), the task additionally creates a tag with the Prefect context dictionary for debugging data downtime issues.<br><br>**Args**:     <ul class="args"><li class="args">`node_name (string, optional)`: the display name of a lineage node.     </li><li class="args">`object_id (string, optional)`: the object ID of a lineage node.     </li><li class="args">`object_type (string, optional)`: the object type of a lineage node - usually,         either "table" or "view".     </li><li class="args">`resource_name (string, optional)`: name of the data warehouse or custom resource.         All resources can be retrieved via a separate task.     </li><li class="args">`lineage_tags (list, optional)`: a list of dictionaries         where each dictionary is a single tag.     </li><li class="args">`api_key_id (string, optional)`: to use this task,         you need to pass the Monte Carlo API credentials.         Those can be created using https://getmontecarlo.com/settings/api.         To avoid passing the credentials         in plain text, you can leverage the PrefectSecret task in your flow.     </li><li class="args">`api_token (string, optional)`: the API token.          To avoid passing the credentials in plain text,          you can leverage the PrefectSecret task in your flow.     </li><li class="args">`prefect_context_tags (bool, optional)`: whether to automatically add a tag         with Prefect context.</li></ul> **Returns**:     <ul class="args"><li class="args">`string`: MCON - a Monte Carlo internal ID of the node.</li></ul></p>|

---
<br>

 ## MonteCarloGetResources
 <div class='class-sig' id='prefect-tasks-monte-carlo-monte-carlo-lineage-montecarlogetresources'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.monte_carlo.monte_carlo_lineage.MonteCarloGetResources</p>(api_key_id=None, api_token=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monte_carlo/monte_carlo_lineage.py#L416">[source]</a></span></div>

Task for querying resources using the Monte Carlo API. You can use this task to find the name of your data warehouse or other resource, and use it as `resource_name` in other Monte Carlo tasks.

**Args**:     <ul class="args"><li class="args">`api_key_id (string, optional)`: to use this task, you need to pass         the Monte Carlo API credentials.         Those can be created using https://getmontecarlo.com/settings/api.         To avoid passing the credentials         in plain text, you can leverage the PrefectSecret task in your flow.     </li><li class="args">`api_token (string, optional)`: the API token.          To avoid passing the credentials in plain text, you can leverage the PrefectSecret task          in your flow.     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-monte-carlo-monte-carlo-lineage-montecarlogetresources-run'><p class="prefect-class">prefect.tasks.monte_carlo.monte_carlo_lineage.MonteCarloGetResources.run</p>(api_key_id=None, api_token=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/monte_carlo/monte_carlo_lineage.py#L446">[source]</a></span></div>
<p class="methods">Retrieve all Monte Carlo resources.<br><br>**Args**:     <ul class="args"><li class="args">`api_key_id (string, optional)`: to use this task,         you need to pass the Monte Carlo API credentials.         Those can be created using https://getmontecarlo.com/settings/api.         To avoid passing the credentials         in plain text, you can leverage the PrefectSecret task in your flow.     </li><li class="args">`api_token (string, optional)`: the API token.          To avoid passing the credentials in plain text, you can leverage the PrefectSecret          task in your flow.</li></ul> **Returns**:     <ul class="args"><li class="args">`list`: Monte Carlo resources, including all existing data warehouses and custom resources.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>