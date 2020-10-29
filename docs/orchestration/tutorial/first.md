# First Flow

## Write Flow

Below is an example flow you may use for this tutorial.

```python
import prefect
from prefect import task, Flow

@task
def hello_task():
    logger = prefect.context.get("logger")
    logger.info("Hello, Cloud!")

flow = Flow("hello-flow", tasks=[hello_task])
```

Note that this Flow can be run locally by calling `flow.run()`, however, it currently does not yet use any of the features provided by the Prefect API.

## Register Flow with the Prefect API

In order to take advantage of the Prefect API for your flow, that flow must first be _registered_. Registration of a flow sends a flow's metadata to the Prefect API in order to support its orchestration.

:::warning Projects
Registering a flow with a backend requires users to organize flows into projects. In this case we are
using the `Hello, World!` Project created in [the "creating a project" tutorial](../concepts/projects.html#creating-a-project).
:::

Add the following line to the bottom of the example flow to register the flow with the Prefect API:

```python
flow.register(project_name="Hello, World!")
```

::: tip Flow Code
Registration only sends data about the existence and format of your flow; **no actual code from the flow is sent to the Prefect API**. Your code remains safe, secure, and private in your own infrastructure!
:::

:::tip Deduplicating registration calls
Each call to `flow.register()` will bump the version of the flow in the backend.
If you are registering flows using automation, you may want to pass an `idempotency_key` which will only create a new version when the key changes.
For example:
```python
MY_INTERNAL_FLOW_VERSION = "1.0.1"
# This constant needs to be manually bumped for re-registration
# and could instead be generated from the last commit to the
# flow file or another indicator

flow.register(
   project_name="Hello, World!",
   idempotency_key=MY_INTERNAL_FLOW_VERSION
)
```
:::

## Run Flow with the Prefect API

Now that your flow is registered with the Prefect API, we will use an Agent to watch for flow runs that are scheduled by the Prefect API and execute them accordingly.

The simplest way to start a [Local agent](/orchestration/agents/local.html) is right from within your script. Add the following line to the bottom of your flow:

```python
flow.run_agent()
```

::: tip Runner Token <Badge text="Cloud"/>
This Local Agent will use the _RUNNER_ token stored in your environment but if you want to manually pass it a token you may do so with `run_agent(token=<YOUR_RUNNER_TOKEN>)`.
:::

Lastly, we need to indicate to the API to schedule a flow run; there are a few options at your disposal to do this:

:::: tabs
::: tab CLI

```bash
prefect run flow --name hello-flow --project 'Hello, World!'
```

:::
::: tab UI
Navigate to the UI and click _Run_ on your flow's page
:::
::: tab "GraphQL API"

```graphql
mutation {
  create_flow_run(input: { flow_id: "<flow id>" }) {
    id
  }
}
```

See [flow runs](/orchestration/concepts/flow_runs.html#flow-runs) for more details.
:::
::: tab Python

```python
from prefect import Client

c = Client()
c.create_flow_run(flow_id="<flow id>")
```

:::
::::

Notice the result of your flow run in the agent output in your terminal.

Remember to stop the agent with `Ctrl-C`.
