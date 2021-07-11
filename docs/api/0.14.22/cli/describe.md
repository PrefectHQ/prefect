---
sidebarDepth: 2
editLink: false
---
# describe
---
### flows
```
Describe a Prefect flow.

Options:
    --name, -n      TEXT    A flow name to query                [required]
    --version, -v   INTEGER A flow version to query
    --project, -p   TEXT    The name of a project to query
    --output, -o    TEXT    Output format, one of {'json', 'yaml'}.
                            Defaults to json.
```

### tasks
```
Describe tasks from a Prefect flow. This command is similar to `prefect
describe flow` but instead of flow metadata it outputs task metadata.

Options:
    --name, -n      TEXT    A flow name to query                [required]
    --version, -v   INTEGER A flow version to query
    --project, -p   TEXT    The name of a project to query
    --output, -o    TEXT    Output format, one of {'json', 'yaml'}.
                            Defaults to json.
```

### flow-runs
```
Describe a Prefect flow run.

Options:
    --name, -n          TEXT    A flow run name to query            [required]
    --flow-name, -fn    TEXT    A flow name to query
    --output, -o        TEXT    Output format, one of {'json', 'yaml'}.
                                Defaults to json.
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>