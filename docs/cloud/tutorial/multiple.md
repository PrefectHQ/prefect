# Multiple Cloud Flows

Running an in-process Agent is simple when developing a single Flow. A more scalable approach is to use the CLI to run a standalone Local Agent that can execute multiple Flows at a time scheduled by Prefect Cloud.

## Run an Agent Manually

Let's introduce another Flow for this tutorial:

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

In another terminal, start the Local Agent:

```bash
prefect agent start
```


::: tip Runner Token
This Local Agent will use the _RUNNER_ token stored in your environment but if you want to manually pass it a token you may do so with `--token <COPIED_RUNNER_TOKEN>`.
:::

Now you have a Local Agent running which can execute multiple Flows that you register with Prefect Cloud:

```bash
prefect run cloud --name hello-flow --project 'Hello, World!'
prefect run cloud --name second-flow --project 'Hello, World!'
```

## Install a Supervised Agent

The standalone Local Agent is ideal for executing Flows decoupled from the scripts defining these Flows. To install the CLI agent in an always-running capacity we recommend using [Supervisor](http://supervisord.org/introduction.html) to monitor the Local Agent:

```bash
pip install supervisor
```

Note: For more information on Supervisor installation visit the [documentation](http://supervisord.org/installing.html).

The Prefect CLI has an installation command for the Local Agent which will output a `supervisord.conf` file that you can save and run using Supervisor.

```bash
prefect agent install local --token <YOUR_RUNNER_TOKEN> > supervisord.conf
```

In that same directory as the `supervisord.conf` file you may start Supervisor.

```bash
supervisord
```

Your Local Agent is now up and running in the background with Supervisor! For more information on the Local Agent and using it with Supervisor visit the [documentation](/cloud/agent/local.html).
