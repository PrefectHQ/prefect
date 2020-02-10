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
@task
def my_task():
    logger = prefect.context.get("logger")

    logger.info("An info message.")
    logger.warning("A warning message.")
```

::: tip Make sure to only access context while your task is running
The Prefect `context` is populated when your task runs. Therefore, you should only access the context logger while your task is running. For example, this WON'T work:

```python
logger = prefect.context.get("logger")

@task
def my_task():

    logger.info("An info message.")
    logger.warning("A warning message.")
```

:::
