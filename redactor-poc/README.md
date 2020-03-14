# Redactor Proof of Concept - Std Logging
Focus on redacting Task log messages and TaskRunner uncaught exceptions by reconfiguring the 
standard logging subsystem.  Redact the logging messages that would go to the CloudHandler and
thus expose sensitive data to the Prefect Cloud database.  The redacted messages are updated
with a URL for the file location where the unredacted messages are stored.

## Methodology
### Task Logging
1. Replace the formatter on the CloudHandler on the Task logger with one that replaces the message with
the local file URI.
1. Add an additional handler to the Task logger that writes the unredacted message to the local file with 
the same URI that was formatted for the CloudHandler.

### TaskRunner Exception
1. Replace the formatter on the CloudHandler on the Task logger with one that replaces the message with
the local file URI.  This formatter also looks for exc_info on the log record and strips it from the
message.
1. Add an additional handler to the Task logger that writes the unredacted message to the local file with 
the same URI that was formatted for the CloudHandler.

## Implementation
In the end the same formatter can be used for both the Task Logging and the TaskRunner Exception.  Skipping
the code for generating the URI the formatter and handler are as follows.

```python
class Formatter(Formatter):
    """
    Formatter to redact log messages by replacing the message with the URI of a local file
    the contains the unredacted message.
    """
    def __init__(self, root_dir, format=None, datefmt=None, style="%"):
        """
        Initialize the formatter with information about the root directory to write log messages.
        Args:
            root_dir: Root directory for unredacted log messages.
            format: Format of the message portion of the log record.
            datefmt: Date format.
            style: Message Style.
        """
        super().__init__(format, datefmt, style)
        self._root_dir = root_dir

    def format(self, record: LogRecord) -> str:
        """
        Format a redacted version of the log record.

        Args:
            record: Log record to format.

        Returns: Formatted and redacted message
        """
        msg = super().format(record)
        if record.exc_info:
            # Strip off the exception information.   Not a very elegant solution
            # but it gets the job done.
            msg = msg.split("Redacted")[0]
            msg += "Redacted Exception"
        path = LocalFileRedactor.redacted_uri(record, self._root_dir)
        redacted_msg = msg + "\n" + path
        return redacted_msg
```

```python
class Handler(Handler):
    """
    Log handler that writes each individual message to a local file.
    """
    def __init__(self, root_dir):
        """
        Initialize the handler with the root directory to write the log messages.

        Args:
            root_dir: Root directory for unredacted log messages.
        """
        super().__init__()
        self._root_dir = root_dir

    def emit(self, record: LogRecord):
        """
        Format and write the unredacted log message to the local file system.

        Args:
            record: Log record to format.
        """
        msg = self.format(record)
        path = Path(LocalFileRedactor.redacted_path(record, self._root_dir))
        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open("wt") as fh:
            fh.write(msg + "\n")
```

The logging configuration for this in the PoC.
```yaml
---
version: 1
disable_existing_loggers: true

formatters:
    standard:
        format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    filename_redactor:
        (): redactor.local_file_redactor.LocalFileRedactor.Formatter
        root_dir: /tmp
        format: "%(asctime)s - %(name)s - %(levelname)s - Redacted"


handlers:
    console:
        class: logging.StreamHandler
        formatter: filename_redactor
        stream: ext://sys.stdout

    file_redactor:
        (): redactor.local_file_redactor.LocalFileRedactor.Handler
        root_dir: /tmp
        formatter: standard


loggers:
    Task:
        level: INFO
        handlers:
          - console
          - file_redactor
        propagate: false

    TaskRunner:
        level: INFO
        handlers:
          - console
          - file_redactor
        propagate: false

root:
    level: NOTSET
    handlers:
      - console
...
```

##Output
### StdOut (Proxy for what CloudHandler would generate)
```text
2020-03-14 17:13:36,851 - Task - INFO - Redacted
file:///tmp/Redactor/2020-03-14T17-13-36.845668/2020-03-14_17-13-36-851.log

2020-03-14 17:13:36,860 - TaskRunner - ERROR - Redacted Exception
file:///tmp/Redactor/2020-03-14T17-13-36.845668/2020-03-14_17-13-36-860.log
```

### Log Message: file:///tmp/Redactor/2020-03-14T17-13-36.845668/2020-03-14_17-13-36-851.log
2020-03-14 17:13:36,851 - Task - INFO - Simple message

### Exception Message: file:///tmp/Redactor/2020-03-14T17-13-36.845668/2020-03-14_17-13-36-860.log
2020-03-14 17:13:36,860 - TaskRunner - ERROR - Uncaught exception
Traceback (most recent call last):
  File "/home/nate/projects/prefect/redactor-poc/src/redactor/tasks.py", line 17, in task_runner
    task()
  File "/home/nate/projects/prefect/redactor-poc/src/redactor/tasks.py", line 12, in task_uncaught_exception
    1 / 0
ZeroDivisionError: division by zero
