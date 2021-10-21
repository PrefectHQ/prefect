---
sidebarDepth: 2
editLink: false
---
# get
---
### flows
```
Query information regarding your Prefect flows.

Options:
    --name, -n      TEXT    A flow name to query
    --version, -v   TEXT    A flow version to query
    --project, -p   TEXT    The name of a project to query
    --limit, -l     INTEGER A limit amount of flows to query, defaults to 10
    --all-versions          Output all versions of a flow, default shows most recent
```

### tasks
```
Query information regarding your Prefect tasks.

Options:
    --name, -n          TEXT    A task name to query
    --flow-name, -fn    TEXT    A flow name to query
    --flow-version, -fv INTEGER A flow version to query
    --project, -p       TEXT    The name of a project to query
    --limit, -l         INTEGER A limit amount of tasks to query, defaults to 10
```

### projects
```
Query information regarding your Prefect projects.

Options:
    --name, -n      TEXT    A project name to query
```

### flow-runs
```
Query information regarding Prefect flow runs.

Options:
    --limit, l          INTEGER A limit amount of flow runs to query, defaults to 10
    --flow, -f          TEXT    Name of a flow to query for runs
    --project, -p       TEXT    Name of a project to query
    --started, -s               Only retrieve started flow runs, default shows `Scheduled` runs
```

### logs
```
Query logs for a flow run.

Note: at least one of `name` or `id` must be specified. If only `name` is
set then the most recent flow run with that name will be queried.

Options:
    --name, -n      TEXT    A flow run name to query
    --id            TEXT    A flow run ID to query
    --info, -i              Retrieve detailed logging info
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>