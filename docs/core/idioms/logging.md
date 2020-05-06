# Logging configuration and usage

Prefect natively ships with a default logger configured to handle the management of logs. More information on logging in Prefect can be found in the [logging concept document](/core/concepts/logging.html).

### Configure the logger

The default Prefect logger can be configured by adjusting the settings found in [Prefect's config](/core/concepts/configuration.html).

```toml
[logging]
# The logging level: NOTSET, DEBUG, INFO, WARNING, ERROR, or CRITICAL
level = "INFO"

# The log format
format = "[%(asctime)s] %(levelname)s - %(name)s | %(message)s"

# additional log attributes to extract from context
# e.g., log_attributes = "['context_var']"
log_attributes = "[]"

# the timestamp format
datefmt = "%Y-%m-%d %H:%M:%S"

# Send logs to Prefect Cloud
log_to_cloud = false

# Extra loggers for Prefect log configuration
extra_loggers = "[]"
```

### Logging from within tasks

The Prefect logger can be used within tasks but the way it is used depends on the API—functional or imperative—that you choose to write your tasks with.

If using the functional API to declare your tasks using the `@task` decorator then the logger can be instantiated by grabbing it from [context](/core/concepts/execution.html):

```python
@task
def my_task():
    logger = prefect.context.get("logger")

    logger.info("An info message.")
    logger.warning("A warning message.")
```

If using the imperative API to declare your tasks as classes then the logger can be used directly from `self.logger`:

```python
class MyTask(prefect.Task):
    def run(self):
        self.logger.info("An info message.")
        self.logger.warning("A warning message.")
```

### Logging stdout

Tasks also provide an optional argument to toggle the logging of stdout—`log_stdout`. This means that, if enabled, anytime you send output to stdout (such as `print()`) it will be logged using the Prefect logger. This option is disabled by default because this option [might not be suitable](https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stdout) for certain types of tasks.

:::: tabs
::: tab "Functional API"
```python
from prefect import task, Flow

@task(log_stdout=True)
def my_task():
    print("This will be logged!")

flow = Flow("log-stdout", tasks=[my_task])
```
:::

::: tab "Imperative API"
```python
from prefect import Task, Flow

class MyTask(Task):
    def run(self):
        print("This will be logged!")

flow = Flow("log-stdout")

my_task = MyTask(log_stdout=True)
flow.add_task(my_task)
```
:::
::::

### Logging with a backend

If you are deploying your flows with the use of a backend such as Prefect Core's server or Prefect Cloud then there are a couple subtle configuration changes that you might happening on each run. First, the configuration option `log_to_cloud` will be set to `True`. This means that the logs from your flow will be sent to the backend where they can be digested and managed. Second, the logging level will always be set to `DEBUG`. This is to ensure that the maximal amount of information is provided in case something goes wrong. The debug logs can always be filtered out after via the UI or API.

Logging can _also_ be disabled for backend runs when providing the `--no-cloud-logs` flag when starting a Prefect agent from the CLI.
