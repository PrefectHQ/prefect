import cloudpickle
import tempfile

from typing import Any


class ResultHandler:
    def deserialize(self, loc: str) -> Any:
        raise NotImplementedError()

    def serialize(self, result: Any) -> str:
        raise NotImplementedError()


class LocalResultHandler(ResultHandler):
    """
    Hook for storing and retrieving task results from local file storage. Only intended to be used
    for local testing and development.
    """

    def __init__(self, dir: str = None):
        self.dir = dir

    def deserialize(self, fpath: str) -> Any:
        with open(fpath, "rb") as f:
            return cloudpickle.loads(f.read())

    def serialize(self, result: Any) -> str:
        fd, loc = tempfile.mkstemp(prefix="prefect-", dir=self.dir)
        with open(fd, "wb") as f:
            f.write(cloudpickle.dumps(result))
        return loc
