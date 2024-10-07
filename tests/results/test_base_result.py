import pytest

from prefect.results import BaseResult


class ConcreteResult(BaseResult[int]):
    def get(self) -> int:
        return 1


def test_lookup_type_fails_gracefully():
    with pytest.raises(ValueError, match="Invalid type: test"):
        ConcreteResult(type="test")
