---
description: Use filters to customize the display of flows and tasks in the Prefect UI.
tags:
    - Orion
    - UI
    - API
    - Prefect Cloud
    - filters
    - settings
---

# Filters

The Filters area at the top of the dashboard provides controls that enable you to display selected details of flow runs on the dashboard. Filters include flow run state, tags, time, and more. 

![Highlighting the filters section of the dashboard.](/img/ui/orion-dash-filters.png)

In the Filters area you can:

- Enter [filter strings](#filter-strings) in the Filter bar for fine-grained filtering.
- Click the **Failed Runs** button to automatically filter on runs that ended in a Failed state.
- Click the **Late Runs** button to filter on runs that remain in a Scheduled past the scheduled start time.
- Click the **Upcoming Runs** button to filter on scheduled runs.

![Filtering the dashboard to show failed runs.](/img/ui/orion-filters-failed.png)

For more filter options, click the **Filters** control to open the filters panel.

![The filters panel enables manually setting filters within the UI.](/img/ui/orion-filters-panel.png)

You can create more granular filters based on:

- Tags
- State
- Timeframes


## Filter behavior

The default behavior of the filter bar UI depends on what page you're viewing in the UI. 

### Dashboard page

When on the dashboard, default filter behavior will be oriented towards flow runs:

- Any text entered into the filter bar without a specified prefix will be applied as a flow name filter. For example, if you enter "etl" in the search bar, the query will return all the flows with the name "etl" as well as all of the deployments, flow runs, and task runs for those flows.
- State filters will apply to flow run states by default.
- Start time filters will apply to flow run start times by default.

### Flow run page

When on the flow run page, default filter behavior will be oriented towards task runs:

- Any text entered into the filter bar without a specified prefix will be applied as a contains filter to task names. 
- State filters will apply to task run states by default.
- Start time filters will apply to task run start times by default.

## Tag inheritance

The most flexible part of the Orion's metadata structure is tags. You can filter flows, flow runs, task runs, and deployments by associated tags. 

To simplify the filtering experience, the tags of all parent entities will be inherited by all of their child entities. Task runs will inherit the tags of their parent flow runs, which will inherit the tags of their deployments, which will inherit the tags of their flows. 

## Filter strings

You can specify precise filters directly in the filter bar by using filter string prefixes. For example:

```
tag:database
```

Within the context of a single filter value, all logic is OR logic: `tag:database|dbt` returns all entities associated with either a `database` tag or a `dbt` tag). 

Across filter values, all logic is AND logic: `tag:database` and `flow:etl` returns all entities that are both associated with a flow with `etl` in the name and have a `database` tag.

String values are always applied as a contains filter, unless they are surrounded by quotes, in which case they are applied as an exactly equal to filter.

| Full | Short | Behavior |
| --- | --- | --- |
| `deployment:` | `d:` | Returns all deployments with names that contain the string. | 
| `deployment_tag:` | `dt:` | Returns all deployments with all of the specified tags. |
| `flow:` | `f:` | Returns all flows with names that contain the string. |
| `flow_run:` | `fr:` | Returns all flow runs with names that contain the string. |
| `flow_run_after:` | `fra:` | Returns all flow runs that started after or on a specific date or time. |
| `flow_run_before:` | `frb:` | Returns all flow runs that started before or on a specific date or time. |
| `flow_run_newer:` | `frn:` | Returns all flow runs that started after the relative period using h (hour), d (day), w (week), m (month), and y (year). |
| `flow_run_older:` | `fro:` | Returns all flow runs that started before the relative period using h (hour), d (day), w (week), m (month), and y (year). |
| `flow_run_state:` | `frs:` | Returns all flow runs with the specified states. |
| `flow_run_tag:` | `frt:` | Returns all flow runs with all of the specified tags. |
| <span class="no-wrap">`flow_run_upcoming:`</span> | <span class="no-wrap">`fru:`</span> | Returns all flow runs scheduled to start before the relative period using h (hour), d (day), w (week), m | (month), and y (year). |
| `flow_tag:` | `ft:` | Returns all flows with all of the specified tags. |
| `tag:` | `t:` | Returns all entities with the specified tags. |
| `task_run:` | `tr:` | Returns all task runs with names that contain the string. |
| `task_run_after:` | `tra:` | Returns all task runs that started after or on a specific date or time. |
| `task_run_before:` | `trb:` | Returns all task runs that started before or on a specific date or time. |
| `task_run_newer:` | `trn:` | Returns all task runs that started after the relative period using h (hour), d (day), w (week), m (month), and y (year). |
| `task_run_older:` | `tro:` | Returns all task runs that started before the relative period using h (hour), d (day), w (week), m (month), and y (year). |
| `task_run_state:` | `trs:` | Returns all task runs with the specified states. |
| `task_run_tag:` | `trt:` | Returns all task runs with all of the specified tags. |
| `version:` | `v:` | Returns all flow runs with the specified version. |