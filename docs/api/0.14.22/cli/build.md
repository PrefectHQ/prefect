---
sidebarDepth: 2
editLink: false
---
# build
---
### build
```
Build one or more flows.

  This command builds all specified flows and writes their metadata to a
  JSON file. These flows can then be registered without building later by
  passing the `--json` flag to `prefect register`.

Options:
  -p, --path TEXT    A path to a file or a directory containing the flow(s) to
                     build. May be passed multiple times to specify multiple
                     paths.

  -m, --module TEXT  A python module name containing the flow(s) to build. May
                     be passed multiple times to specify multiple modules.

  -n, --name TEXT    The name of a flow to build from the specified
                     paths/modules. If provided, only flows with a matching
                     name will be built. May be passed multiple times to
                     specify multiple flows. If not provided, all flows found
                     on all paths/modules will be built.

  -l, --label TEXT   A label to add on all built flow(s). May be passed
                     multiple times to specify multiple labels.

  -o, --output TEXT  The output path. Defaults to `flows.json`.
  -u, --update       Updates an existing `json` file rather than overwriting
                     it.

  --help             Show this message and exit.

  Examples:

    Build all flows found in a directory.

      $ prefect build -p myflows/

    Build a flow named "example" found in `flow.py`.

      $ prefect build -p flow.py -n "example"

    Build all flows found in a module named `myproject.flows`.

      $ prefect build -m "myproject.flows"
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>