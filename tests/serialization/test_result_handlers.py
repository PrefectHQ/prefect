import pytest

from prefect.engine.result_handlers import ResultHandler, LocalResultHandler
from prefect.serialization.result_handlers import ResultHandlerSchema


def test_serialize_base_result_handler():
    serialized = ResultHandlerSchema().dump(ResultHandler())
    assert isinstance(serialized, dict)
    assert serialized["type"] == "ResultHandler"


def test_deserialize_base_result_handler():
    schema = ResultHandlerSchema()
    obj = schema.load(schema.dump(ResultHandler()))
    assert isinstance(obj, ResultHandler)
    assert hasattr(obj, "logger")
    assert obj.logger.name == "prefect.ResultHandler"


def test_serialize_local_result_handler_with_no_dir():
    serialized = ResultHandlerSchema().dump(LocalResultHandler())
    assert isinstance(serialized, dict)
    assert serialized["type"] == "LocalResultHandler"
    assert serialized["dir"] is None


def test_serialize_local_result_handler_with_dir():
    serialized = ResultHandlerSchema().dump(LocalResultHandler(dir="/root/prefect"))
    assert isinstance(serialized, dict)
    assert serialized["type"] == "LocalResultHandler"
    assert serialized["dir"] == "/root/prefect"


@pytest.mark.parametrize("dir", [None, "/root/prefect"])
def test_deserialize_local_result_handler(dir):
    schema = ResultHandlerSchema()
    obj = schema.load(schema.dump(LocalResultHandler(dir=dir)))
    assert isinstance(obj, LocalResultHandler)
    assert hasattr(obj, "logger")
    assert obj.logger.name == "prefect.LocalResultHandler"
    assert obj.dir == dir
