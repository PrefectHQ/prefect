from pydantic import BaseModel

from prefect.types import KeyValueLabels


def test_allow_none_as_empty_dict():
    class Model(BaseModel):
        labels: KeyValueLabels

    assert Model(labels=None).labels == {}  # type: ignore
