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
    def redacted_url(cls, record: LogRecord, root_dir: str) -> str:
        return "file://" + cls.redacted_path(record, root_dir)

    class Formatter(Formatter):
        def __init__(self, root_dir, format=None, datefmt=None, style="%"):
            super().__init__(format, datefmt, style)
            self._root_dir = root_dir

        def format(self, record: LogRecord):
            msg = super().format(record)
            if record.exc_info:
                msg = msg.split("Redacted")[0]
                msg += "Redacted Exception"
            path = LocalFileRedactor.redacted_url(record, self._root_dir)
            redacted_msg = msg + "\n" + path
            return redacted_msg

    class Handler(Handler):
        def __init__(self, root_dir):
            super().__init__()
            self._root_dir = root_dir

        def emit(self, record: LogRecord):
            msg = self.format(record)
            path = Path(LocalFileRedactor.redacted_path(record, self._root_dir))
            path.parent.mkdir(exist_ok=True, parents=True)
            with path.open("wt") as fh:
                fh.write(msg + "\n")
