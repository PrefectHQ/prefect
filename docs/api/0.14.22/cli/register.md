---
sidebarDepth: 2
editLink: false
---
# register
---
### register
```
Register one or more flows into a project.

  Flows with unchanged metadata will be skipped as registering again will
  only change the version number.

Options:
  --project TEXT     The name of the Prefect project to register this flow in.
                     Required.

  -p, --path TEXT    A path to a file or a directory containing the flow(s) to
                     register. May be passed multiple times to specify
                     multiple paths.

  -m, --module TEXT  A python module name containing the flow(s) to register.
                     May be the full import path to a flow. May be passed
                     multiple times to specify multiple modules.

  -j, --json TEXT    A path or URL to a JSON file created by `prefect build`
                     containing the flow(s) to register. May be passed
                     multiple times to specify multiple paths. Note that this
                     path may be a remote url (e.g. https://some-
                     url/flows.json).

  -n, --name TEXT    The name of a flow to register from the specified
                     paths/modules. If provided, only flows with a matching
                     name will be registered. May be passed multiple times to
                     specify multiple flows. If not provided, all flows found
                     on all paths/modules will be registered.

  -l, --label TEXT   A label to add on all registered flow(s). May be passed
                     multiple times to specify multiple labels.

  -f, --force        Force flow registration, even if the flow's metadata is
                     unchanged.

  --watch            If set, the specified paths and modules will be monitored
                     and registration re-run upon changes.

  --help             Show this message and exit.

  Examples:

    Register all flows found in a directory.

      $ prefect register --project my-project -p myflows/

    Register a flow named "example" found in `flow.py`.

      $ prefect register --project my-project -p flow.py -n "example"

    Register all flows found in a module named `myproject.flows`.

      $ prefect register --project my-project -m "myproject.flows"

    Register a flow in variable `flow_x` in a module `myproject.flows`.

      $ prefect register --project my-project -m "myproject.flows.flow_x"

    Register all pre-built flows from a remote JSON file.

      $ prefect register --project my-project --json https://some-
  url/flows.json

    Watch a directory of flows for changes, and re-register flows upon
  change.

      $ prefect register --project my-project -p myflows/ --watch
```

### register flow
```
Register a flow (DEPRECATED)

Options:
  --help  Show this message and exit.
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>