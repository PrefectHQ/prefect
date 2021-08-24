# Parameters & Mapped Tasks

Writing a flow to greet one person is all good, but if the requirements change, prefect can still help you. Let's say:

- You now need to greet multiple people
- You need the list of people to be configurable

In [the core ETL tutorial](/core/tutorial/03-parameterized-flow.md) we cover how
to do this using [parameters](/core/concepts/parameters.md) and [mapped
tasks](/core/concepts/mapping.md). These concepts work equally well when run
using a Prefect backend.

## Update Your Flow

After a few minutes of editing, you might come up with a flow that looks
something like this:

```python
import prefect
from prefect import task, Flow, Parameter

@task
def say_hello(name):
    logger = prefect.context.get("logger")
    logger.info(f"Hello, {name}!")

with Flow("hello-flow") as flow:
    # An optional parameter "people", with a default list of names
    people = Parameter("people", default=["Arthur", "Ford", "Marvin"])
    # Map `say_hello` across the list of names
    say_hello.map(people)

# Register the flow under the "tutorial" project
flow.register(project_name="tutorial")
```

This flow has an optional parameter `people` that takes in a list of names to
greet (with a default list provided). It then maps the `say_hello` task over
the list of names.

Run the above to register a new version of `hello-flow`. This will archive the
old version and register a new version using the new code.

## Execute a Flow Run

As in the [previous section](./registerings-and-running-a-flow.md#execute-a-flow-run), you can execute a
flow run using the "Quick Run" button in the UI. Make sure you still have your
Agent running [from before](./registering-and-running-a-flow.md#start-an-agent).

After a few seconds, you should see your flow run complete successfully.

![](/orchestration/tutorial/hello-flow-run-mapped1.png)

This run has a few more tasks than before (one `people` parameter task, and
several mapped `say_hello` tasks). Since we used the parameter defaults, we
should see 3 mapped `say_hello` tasks, one for each name.

Click through the logs tab to see the logs for each name.

## Specify New Parameters

To start a flow run with non-default values for a parameter, you can click the
`"Run"` button (middle of the flow page) instead of the `"Quick Run"` button.
This brings you to a [run
page](/orchestration/ui/flow.html#run) where you can
configure more details for a specific flow run. Here we'll set the flow run
name to `"custom-names"`, and provide new values for the `"people"` parameter.

![](/orchestration/tutorial/hello-flow-run-parameter-config.png)

When you're happy with the flow run settings, click `"Run"` to create a new
flow run using the new settings.

Once the flow run starts, check the logs to see that your settings took effect.

![](/orchestration/tutorial/hello-flow-run-mapped2.png)

Custom parameters for a flow run can also be specified programmatically, see
the [flow run docs](/orchestration/concepts/flow_runs.md) for more information.



