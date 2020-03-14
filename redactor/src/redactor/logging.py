from datetime import datetime
from logging import LogRecord, Formatter, Handler
from pathlib import Path


def datetime_to_path_str(time) -> str:
    return time.isoformat().replace(":", "-")


def asctime_to_path_str(time: str) -> str:
    return time.replace(":", "-").replace(",", "-").replace(" ", "_")


def redacted_path(record: LogRecord, root_dir: str):
    filename = (
        f"{root_dir}/"
        f"{record.flow_name}/"
        f"{datetime_to_path_str(record.started)}/"
        f"{asctime_to_path_str(record.asctime)}.log"
    )
    return filename


def redacted_url(record: LogRecord, root_dir: str) -> str:
    return "file://" + redacted_path(record, root_dir)


class FileRedactorFormatter(Formatter):
    def __init__(self, root_dir, format=None, datefmt=None, style="%"):
        super().__init__(format, datefmt, style)
        self._root_dir = root_dir

    def format(self, record: LogRecord):
        msg = super().format(record)
        if record.exc_info:
            msg = msg.split("Redacted")[0]
            msg += "Redacted Exception"
        path = redacted_url(record, self._root_dir)
        redacted_msg = msg + "\n" + path
        return redacted_msg


class FileRedactorHandler(Handler):
    def __init__(self, root_dir):
        super().__init__()
        self._root_dir = root_dir

    def emit(self, record: LogRecord):
        msg = self.format(record)
        path = Path(redacted_path(record, self._root_dir))
        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open("wt") as fh:
            fh.write(msg + "\n")
