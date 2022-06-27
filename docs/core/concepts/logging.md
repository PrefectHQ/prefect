# Logging

Prefect has a variety of ways to generate logs from tasks.

## Logging Configuration

Prefect's log levels are governed by `prefect.config.logging.level`, which defaults to `INFO`. However, this setting only affects "Prefect" loggers, not Python loggers globally.

To change the default log level, set the environment variable `PREFECT__LOGGING__LEVEL=DEBUG`.

## Prefect Loggers

To access a Prefect-configured logger, use `prefect.utilities.logging.get_logger(<optional name>)`. If you don't provide a name, you'll receive the root Prefect logger.

## Logging from Tasks

### Task Classes

To log from a task class, use `self.logger`:

```python
class MyTask(prefect.Task):
    def run(self):
        self.logger.info("An info message.")
        self.logger.warning("A warning message.")
```

### Task Decorators

To log from a task generated with an @task decorator, access the `logger` from context while your task is running:

```python
import prefect

@task
def my_task():
    logger = prefect.context.get("logger")

    logger.info("An info message.")
    logger.warning("A warning message.")
```

!!! tip Make sure to only access context while your task is running
    The Prefect `context` is populated when your task runs. Therefore, you should only access the context logger while your task is running. For example, this WON'T work:

    ```python
    logger = prefect.context.get("logger")

    @task
    def my_task():

        logger.info("An info message.")
        logger.warning("A warning message.")
    ```
    Note, pickling context objects is explicitly not supported. You should always access context as an attribute of the `prefect` module. For example, this WON'T work:
    ```python
    from prefect import context

    @task
    def my_task():
        logger = context.get("logger") # will not work
        logger.info("An info message.")
        logger.warning("A warning message.")
    ```

:::

### Logging stdout

Prefect tasks natively support forwarding the output of stdout to a logger. This can be enabled by setting `log_stdout=True` on your task.

```python
@task(log_stdout=True)
def log_my_stdout():
    print("I will be logged!")
```

### Extra Loggers

Many libraries like `boto3` and `snowflake.connector` are setup to emit their own internal logs when configured with a logging configuration. You may even have an internal shared library for your team with the same functionality.

If you are doing this via the standard `logging` library you might do this:

```python
import logging
import sys
for l in ['snowflake.connector', 'boto3', 'custom_lib']:
    logger = logging.getLogger(l)
    logger.setLevel('INFO')
    log_stream = logging.StreamHandler(sys.stdout)
    log_stream.setFormatter(LOG_FORMAT)
    logger.addHandler(log_stream)
```

Given that Prefect already provides a way to configure logging for local and cloud, you can provide these extra loggers to have them inherit the Prefect logging config to stream locally and also show up in cloud.

In order for this to work you need to provide a list to `prefect.config.logging.extra_loggers`.

Here is what the TOML config will look like:

```toml
[logging]
# Extra loggers for Prefect log configuration
extra_loggers = "['snowflake.connector', 'boto3', 'custom_lib']"
```

As an environment variable:

```bash
export PREFECT__LOGGING__EXTRA_LOGGERS="['snowflake.connector', 'boto3', 'custom_lib']"
```