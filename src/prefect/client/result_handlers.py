import base64
import cloudpickle
import tempfile

from typing import Any

from prefect import config
from prefect.client.client import Client


class ResultHandler:
    def deserialize(self, loc: str) -> Any:
        raise NotImplementedError()

    def serialize(self, result: Any) -> str:
        raise NotImplementedError()


class CloudResultHandler(ResultHandler):
    def __init__(self) -> None:
        self.client = Client()
        self.result_handler_service = config.cloud.result_handler

    def deserialize(self, uri: str) -> Any:
        res = self.client.get("/", server=self.result_handler_service, **{"uri": uri})

        try:
            return_val = cloudpickle.loads(base64.b64decode(res.get("result", "")))
        except EOFError:
            return_val = None

        return return_val

    def serialize(self, result: Any) -> str:
        binary_data = base64.b64encode(cloudpickle.dumps(result)).decode()
        res = self.client.post(
            "/", server=self.result_handler_service, **{"result": binary_data}
        )
        return res.get("uri", "")


class LocalResultHandler(ResultHandler):
    """
    Hook for storing and retrieving task results from local file storage. Only intended to be used
    for local testing and development. Task results are serialized using `cloudpickle` and stored in the
    provided location for use in future runs.

    **NOTE**: Stored results will _not_ be automatically cleaned up after execution.

    Args:
        - dir (str, optional): the _absolute_ path to a directory for storing
            all results; defaults to `$TMPDIR`
    """

    def __init__(self, dir: str = None):
        self.dir = dir

    def deserialize(self, fpath: str) -> Any:
        """
        Deserialize a result from the given file location.

        Args:
            - fpath (str): the _absolute_ path to the location of a serialized result

        Returns:
            - the deserialized result from the provided file
        """
        with open(fpath, "rb") as f:
            return cloudpickle.loads(f.read())

    def serialize(self, result: Any) -> str:
        """
        Serialize the provided result to local disk.

        Args:
            - result (Any): the result to serialize and store

        Returns:
            - str: the _absolute_ path to the serialized result on disk
        """
        fd, loc = tempfile.mkstemp(prefix="prefect-", dir=self.dir)
        with open(fd, "wb") as f:
            f.write(cloudpickle.dumps(result))
        return loc
