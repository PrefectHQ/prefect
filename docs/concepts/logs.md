# Logging

Prefect enables you to log a variety of useful information about your flow and task runs, capturing information about your workflows for purposes such as monitoring, troubleshooting, and auditing.

Prefect captures logs for your flow and task runs by default, even if you have not started an Orion API server with `prefect orion start`.

You can view and filter logs in the Orion UI, or access log records via the API or CLI.

Prefect enables fine-grained customization of log levels for flows and tasks, including configuration for default levels and log message formatting.

## Logging overview

Whenever you run a flow, Prefect automatically logs events for flow runs and task runs, along with any custom log handlers you have configured. No configuration is needed to enable Prefect logging.

For example, say you created a simple flow in a file flow.py. If you create a local flow run with `python flow.py`, you'll see an example of the log messages created automatically by Prefect:

```bash
$ python flow.py
16:45:44.534 | INFO    | prefect.engine - Created flow run 'gray-dingo' for flow 
'hello-flow'
16:45:44.534 | INFO    | Flow run 'gray-dingo' - Using task runner 'SequentialTaskRunner'
16:45:44.598 | INFO    | Flow run 'gray-dingo' - Created task run 'hello-task-54135dc1-0' 
for task 'hello-task'
Hello world!
16:45:44.650 | INFO    | Task run 'hello-task-54135dc1-0' - Finished in state 
Completed(None)
16:45:44.672 | INFO    | Flow run 'gray-dingo' - Finished in state 
Completed('All states completed.')
```

You can see logs for the flow run in the Orion UI by navigating to the flow run and selecting the **Logs** tab.

![Viewing logs for a flow run in the Orion UI](/img/concepts/flow_run_logs.png)

Prefect supports the standard Python logging levels `CRITICAL`, `ERROR`, `WARNING`, `INFO`, and `DEBUG`. By default, Prefect logs `INFO`-level events. You can configure the root logging level as well as specific logging levels for flow and task runs.

## Logging Configuration

There is a /prefect/logging/logging.yml file packaged with Prefect that defines the default logging configuration. You can override any logging configuration by setting an environment variable using the syntax `PREFECT_LOGGING_[PATH]_[TO]_[KEY]`, with `[PATH]_[TO]_[KEY]` corresponding to the nested address of any setting in logging.yml. 

For example, to change the default logging levels for Prefect to `DEBUG`, you can set the environment variable `PREFECT_LOGGING_LOGGERS_ROOT_LEVEL="DEBUG"`.

You can also customize logging configuration by creating your own version of logging.yml with custom settings, then specifying the path to your custom settings file with `PREFECT_LOGGING_SETTINGS_PATH`. (If the file does not exist, Prefect ignores the setting and uses the default configuration.)

Prefect's log levels are governed by `PREFECT_LOGGING_LOGGERS_ROOT_LEVEL`, which defaults to `INFO`. However, this setting only affects Prefect loggers, not Python or other loggers globally.

## Prefect Loggers

To access the Prefect logger, import `from prefect import get_run_logger`. You can send messages to the logger in both flows and tasks.

### Logging in flows

To log from a flow, create an instance of `get_run_logger()`, then call the logger specifying the log level and optional message to log.

```python
from prefect import flow, get_run_logger

@flow(name="log-example-flow")
def logger_flow():
    logger = get_run_logger()
    logger.info("INFO level log message.")
```

Prefect automatically uses the flow run logger based on the flow context. Based on the above code, Prefect captures the following as a log event.

```bash
15:35:17.304 | INFO    | Flow run 'mottled-marten' - INFO level log message.
```

The default flow run log formatter uses the flow run name for log messages.

### Logging in tasks

Logging in tasks works much as logging in flows: create an instance of `get_run_logger()`, then call the logger specifying the log level and optional message to log.

```python
from prefect import flow, task, get_run_logger

@task
def logger_task(name="log-example-task"):
    logger = get_run_logger()
    logger.info("INFO level log message from a task.")

@flow(name="log-example-flow")
def logger_flow():
    logger_task()
```

The default task run log formatter uses the task run name for log messages.

```bash
15:33:47.179 | ERROR   | Task run 'task_one-80a1ffd1-0' - A task level ERROR message.
```

