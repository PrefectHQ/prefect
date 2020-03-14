from logging import LogRecord, Formatter, Handler
from pathlib import Path


class LocalFileRedactor:
    @staticmethod
    def datetime_to_path_str(time) -> str:
        return time.isoformat().replace(":", "-")

    @staticmethod
    def asctime_to_path_str(time: str) -> str:
        return time.replace(":", "-").replace(",", "-").replace(" ", "_")

    @classmethod
    def redacted_path(cls, record: LogRecord, root_dir: str):
        filename = (
            f"{root_dir}/"
            f"{record.flow_name}/"
            f"{cls.datetime_to_path_str(record.started)}/"
            f"{cls.asctime_to_path_str(record.asctime)}.log"
        )
        return filename

    @classmethod
    def redacted_uri(cls, record: LogRecord, root_dir: str) -> str:
        return "file://" + cls.redacted_path(record, root_dir)

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
