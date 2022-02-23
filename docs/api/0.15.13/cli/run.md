---
sidebarDepth: 2
editLink: false
---
# run
---
### run
```
Run a flow

Options:
  -i, --id TEXT                   The UUID of a flow or flow group to run. If
                                  a flow group id is given, the latest flow id
                                  will be used for the run.
  --project TEXT                  The name of the Prefect project containing
                                  the flow to run.
  -p, --path TEXT                 The path to a file containing the flow to
                                  run.
  -m, --module TEXT               The python module name containing the flow
                                  to run.
  -n, --name TEXT                 The name of a flow to run from the specified
                                  file/module/project. If the source contains
                                  multiple flows, this must be provided.
  --label TEXT                    A label to add to the flow run. May be
                                  passed multiple times to specify multiple
                                  labels. If not passed, the labels from the
                                  flow group will be used.
  --run-name TEXT                 A name to assign to the flow run.
  --context TEXT                  A key, value pair (key=value) specifying a
                                  flow context variable. The value will be
                                  interpreted as JSON. May be passed multiple
                                  times to specify multiple context values.
                                  Nested values may be set by passing a dict.
  --param TEXT                    A key, value pair (key=value) specifying a
                                  flow parameter. The value will be
                                  interpreted as JSON. May be passed multiple
                                  times to specify multiple parameter values.
  --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  The log level to set for the flow run. If
                                  passed, the level must be a valid Python
                                  logging level name. If this option is not
                                  passed, the default level for the flow will
                                  be used.
  --param-file TEXT               The path to a JSON file containing parameter
                                  keys and values. Any parameters passed with
                                  `--param` will take precedence over these
                                  values.
  --idempotency-key TEXT          A key to prevent duplicate flow runs. If a
                                  flow run has already been started with the
                                  provided value, the command will display
                                  information for the existing run. If using
                                  `--execute`, duplicate flow runs will exit
                                  with an error. If not using the backing API,
                                  this flag has no effect.
  --execute                       Execute the flow run in-process without an
                                  agent. If this process exits, the flow run
                                  will be marked as 'Failed'.
  -s, --schedule                  Execute the flow run according to the
                                  schedule attached to the flow. If this flag
                                  is set, this command will wait between
                                  scheduled flow runs. If the flow has no
                                  schedule, this flag will be ignored. If used
                                  with a non-local run, an exception will be
                                  thrown.
  -q, --quiet                     Disable verbose messaging about the flow run
                                  and just print the flow run id.
  --no-logs                       Disable streaming logs from the flow run to
                                  this terminal. Only state changes will be
                                  displayed. Only applicable when `--watch` is
                                  set.
  -w, --watch                     Wait for the flow run to finish executing
                                  and display status information.
  --help                          Show this message and exit.

  Examples:

    Run flow in a script locally

      $ prefect run -p hello-world.py

    Run flow in a module locally

      $ prefect run -m prefect.hello_world

    Run flow with a non-default parameter locally

      $ prefect run -m prefect.hello_world --param name=Marvin

    Run registered flow with the backend by flow name and watch execution

      $ prefect run -n "hello-world" --watch

    Run registered flow with the backend with custom labels

      $ prefect run -n "hello-world" --label example --label hello

    Run registered flow with the backend by flow id and exit after creation

      $ prefect run -i "9a1cd70c-37d7-4cd4-ab91-d41c2700300d"

    Run registered flow and pipe flow run id to another program

      $ prefect run -n "hello-world" --quiet | post_run.sh

    Run registered flow and execute locally without an agent

      $ prefect run -n "hello-world" --execute
```

### run flow
```
Run a flow that is registered to the Prefect API

DEPRECATED: Use `prefect run` instead of `prefect run flow`

Options:
    --id, -i                    TEXT        The ID of a flow to run
    --version-group-id          TEXT        The ID of a flow version group to run
    --name, -n                  TEXT        The name of a flow to run
    --project, -p               TEXT        The name of a project that contains the flow
    --version, -v               INTEGER     A flow version to run
    --parameters-file, -pf      FILE PATH   A filepath of a JSON file containing
                                            parameters
    --parameters-string, -ps    TEXT        A string of JSON parameters (note: to ensure these are
                                            parsed correctly, it is best to include the full payload
                                            within single quotes)
    --run-name, -rn             TEXT        A name to assign for this run
    --context, -c               TEXT        A string of JSON key / value pairs to include in context
                                            (note: to ensure these are parsed correctly, it is best
                                            to include the full payload within single quotes)
    --watch, -w                             Watch current state of the flow run, stream
                                            output to stdout
    --label                     TEXT        Set labels on the flow run; use multiple times to set
                                            multiple labels.
    --logs, -l                              Get logs of the flow run, stream output to
                                            stdout
    --no-url                                Only output the flow run id instead of a
                                            link

Either `id`, `version-group-id`, or both `name` and `project` must be provided to run a flow.

If both `--parameters-file` and `--parameters-string` are provided then the values
passed in through the string will override the values provided from the file.

e.g.
File contains:  {"a": 1, "b": 2}
String:         '{"a": 3}'
Parameters passed to the flow run: {"a": 3, "b": 2}

Example:
    $ prefect run flow -n "Test-Flow" -p "My Project" -ps '{"my_param": 42}'
    Flow Run: https://cloud.prefect.io/myslug/flow-run/2ba3rrfd-411c-4d99-bb2a-f64a6dea78f9
```

### flow
```
Run a flow that is registered to the Prefect API

DEPRECATED: Use `prefect run` instead of `prefect run flow`

Options:
    --id, -i                    TEXT        The ID of a flow to run
    --version-group-id          TEXT        The ID of a flow version group to run
    --name, -n                  TEXT        The name of a flow to run
    --project, -p               TEXT        The name of a project that contains the flow
    --version, -v               INTEGER     A flow version to run
    --parameters-file, -pf      FILE PATH   A filepath of a JSON file containing
                                            parameters
    --parameters-string, -ps    TEXT        A string of JSON parameters (note: to ensure these are
                                            parsed correctly, it is best to include the full payload
                                            within single quotes)
    --run-name, -rn             TEXT        A name to assign for this run
    --context, -c               TEXT        A string of JSON key / value pairs to include in context
                                            (note: to ensure these are parsed correctly, it is best
                                            to include the full payload within single quotes)
    --watch, -w                             Watch current state of the flow run, stream
                                            output to stdout
    --label                     TEXT        Set labels on the flow run; use multiple times to set
                                            multiple labels.
    --logs, -l                              Get logs of the flow run, stream output to
                                            stdout
    --no-url                                Only output the flow run id instead of a
                                            link

Either `id`, `version-group-id`, or both `name` and `project` must be provided to run a flow.

If both `--parameters-file` and `--parameters-string` are provided then the values
passed in through the string will override the values provided from the file.

e.g.
File contains:  {"a": 1, "b": 2}
String:         '{"a": 3}'
Parameters passed to the flow run: {"a": 3, "b": 2}

Example:
    $ prefect run flow -n "Test-Flow" -p "My Project" -ps '{"my_param": 42}'
    Flow Run: https://cloud.prefect.io/myslug/flow-run/2ba3rrfd-411c-4d99-bb2a-f64a6dea78f9
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>