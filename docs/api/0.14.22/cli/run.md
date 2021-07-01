---
sidebarDepth: 2
editLink: false
---
# run
---
### flow
```
Run a flow that is registered to the Prefect API

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
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>