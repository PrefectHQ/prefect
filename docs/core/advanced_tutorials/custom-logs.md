---
sidebarDepth: 0
---

# Deployment: Logging

> How can you customize your Prefect logs?

## Logging

Logging is a crucial aspect of any production environment. Prefect exposes a series of configuration settings and utility functions for customizing the behavior of your logs.

### Adding your own logs

The most common place you might want to add additional logs is within a custom Task. There are two places you can access your Task's logger, depending on how you created the Task:

- if your Task is implemented as a subclass of the `Task` class, the `self.logger` attribute contains your Task's logger
- if your Task is implemented via the `task` decorator, you can access your logger from context: `logger = prefect.context.get("logger")`

### Configuration

Your [Prefect user configuration file](../concepts/configuration.html) provides one way to easily change how logs are presented to you when running locally. In your user config file, add a section for logging with the following structure:

```
[logging]
# The logging level: NOTSET, DEBUG, INFO, WARNING, ERROR, or CRITICAL
level = "INFO"

# The log format
format = "[%(asctime)s] %(levelname)s - %(name)s | %(message)s"
```

Alternatively, you can set the following environment variables:

```bash
export PREFECT__LOGGING__LEVEL="INFO"
export PREFECT__LOGGING__FORMAT="[%(asctime)s] %(levelname)s - %(name)s | %(message)s"
```

### Adding Handlers

In addition to changing how your logs are formatted, you can take it one step further by interacting with the logger objects directly prior to execution. For example, you can add new handlers to your logger (recall that logging handlers allow you to ship your logs to multiple configurable destinations).

This is easily accomplished via the [`get_logger` utility](../../api/latest/utilities/logging.html#prefect-utilities-logging-get-logger) located in `prefect.utilities.logging`. The root logger can be accessed by calling `get_logger()` with no arguments. Note that the `Task` and `Flow` loggers are associated with loggers of the same names as the Task or Flow.

## An Example

Let's walk through a basic example. To begin, we will create a dummy webserver on our local machine that we will POST logs to:

```bash
# spins up a local webserver running at http://0.0.0.0:8000/
python3 -m http.server
```

Next, let's create a logger handler and add this handler to our Task's loggers.

```python
import logging
import requests

import prefect
from prefect import task, Flow
from prefect.utilities.logging import get_logger


class MyHandler(logging.StreamHandler):
    def emit(self, record):
        requests.post("http://0.0.0.0:8000/", params=dict(msg=record.msg))


@task(name="Task A")
def task_a():
    return 3


@task(name="Task B")
def task_b(x):
    logger = prefect.context.get("logger")
    logger.debug("Beginning to run Task B with input {}".format(x))
    y = 3 * x + 1
    logger.debug("Returning the value {}".format(y))
    return y


with Flow("logging-example") as flow:
    result = task_b(task_a)


# now attach our custom handler to Task B's logger
task_logger = get_logger("Task B")
task_logger.addHandler(MyHandler())


if __name__ == "__main__":
    flow.run()
```

If we store this code in a file called `logging_example.py`, we can update our log formats and levels using environment variables and kick off this flow run:

```bash
export PREFECT__LOGGING__LEVEL="DEBUG"
export PREFECT__LOGGING__FORMAT="%(levelname)s - %(name)s | %(message)s"

python logging_example.py
```

We should see our logs posted to stdout, as usual. But if we navigate to the window where our webserver is running, we will also see something like:

```bash
127.0.0.1 - "POST /?msg=Beginning+to+run+Task+B+with+input+3 HTTP/1.1" 501
127.0.0.1 - "POST /?msg=Returning+the+value+10 HTTP/1.1" 501
```

We are seeing 501 status codes because our webserver doesn't implement _any_ routes.

## Further steps

You can take this example further by spinning up a real storage solution for your logs. Additionally, if running on Prefect Cloud, you can opt-in to having Prefect store your logs for you and expose them via a convenient GraphQL interface!
