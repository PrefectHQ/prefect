# Multiple Flows

Running an in-process agent is simple when developing a single flow. A more scalable approach is to use the CLI to run a standalone local agent that can execute multiple flows at a time scheduled by the Prefect API.

## Run an Agent Manually

Let's introduce another flow for this tutorial:

```python
import prefect
from prefect import task, Flow

@task
def another_task():
    logger = prefect.context.get("logger")
    logger.info("Our second Flow!")

flow = Flow("second-flow", tasks=[another_task])

flow.register(project_name="Hello, World!")
```

In another terminal, start the local agent:

```bash
prefect agent local start
```

::: tip Runner Token <Badge text="Cloud"/>
This Local Agent will use the _RUNNER_ token stored in your environment but if you want to manually pass it a token you may do so with `--token <COPIED_RUNNER_TOKEN>`.
:::

Now you have a local agent running which can execute multiple flows that you register with the Prefect API:

```bash
prefect run flow --name hello-flow --project 'Hello, World!'
prefect run flow --name second-flow --project 'Hello, World!'
```

## Install a Supervised Agent

The standalone local agent is ideal for executing flows decoupled from the scripts defining these flows. To install the CLI agent in an always-running capacity we recommend using [Supervisor](http://supervisord.org/introduction.html) to monitor the local agent:

```bash
pip install supervisor
```

Note: For more information on Supervisor installation visit the [documentation](http://supervisord.org/installing.html).

The Prefect CLI has an installation command for the local agent which will output a `supervisord.conf` file that you can save and run using Supervisor.

```bash
prefect agent local install --token <YOUR_RUNNER_TOKEN> > supervisord.conf
```

::: warning No token necessary for Core server
If you are using Prefect Core's server then no `--token` is necessary for this step.
:::

In that same directory as the `supervisord.conf` file you may start Supervisor.

```bash
supervisord
```

Your Local Agent is now up and running in the background with Supervisor! For more information on the Local Agent and using it with Supervisor visit the [documentation](/orchestration/agents/local.html).
