from logging import StreamHandler
from pathlib import Path

from prefect.utilities.context import context


class LocalHandler(StreamHandler):
    """
    Local logging handler that logs the task logging messages to the local file system and
    replaces the logging message with the uri to the file where the massage was logged.  Log
    messages are stored in a directory structure as follows.

    <root-dir>/<flow-name>/<schedule-start-time>/<date>.<full-task-name>.log
    """
    def __init__(self):
        super().__init__()
        # Can't check for the full log path yet as the run context isn't populated.
        self.root_path = Path(context.config.logging.local.root_dir)
        # Probably should add a formatter here, but might not need it as the details
        # are formatted into the Prefect Cloud log.

    @staticmethod
    def date_as_path(date):
        """Clean up a date to make a better path entry."""
        return date.isoformat().replace(":", ".").replace("+", ".")

    def emit(self, record):
        # Only process Task logger messages.  This could be any test that the developer
        # determines is appropriate.   It could possible be a filter.
        if not record.name.startswith("prefect.Task: "):
            return
        # Build the path and make sure it exists.
        log_path = (
            self.root_path
            / context.flow_name
            / self.date_as_path(context.scheduled_start_time)
        )
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = (
            log_path / f"{self.date_as_path(context.date)}-{context.task_full_name}.log"
        )
        # Write the log message.
        with log_file.open("at") as fh:
            fh.write(f"{record.message}\n")
        # Update the message with the URI and remove the sensitive data.
        record.message = f"file://{log_file}"
