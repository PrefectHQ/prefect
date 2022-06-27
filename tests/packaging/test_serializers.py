import pytest

from prefect.packaging.serializers import (
    ImportSerializer,
    PickleSerializer,
    SourceSerializer,
)


def foo(return_val="foo"):
    return return_val


@pytest.mark.parametrize(
    "serializer", [SourceSerializer(), ImportSerializer(), PickleSerializer()]
)
def test_serialize_function(serializer):
    blob = serializer.dumps(foo)
    result = serializer.loads(blob)

    assert type(result) == type(foo)
    assert result.__kwdefaults__ == foo.__kwdefaults__
    assert result.__name__ == foo.__name__

    # The source serializer updates the module to __prefect_loader__
    if not isinstance(serializer, SourceSerializer):
        assert result.__module__ == result.__module__

    assert result() == foo(), "Result should be callable"
