from pydantic import BaseModel

from prefect.types import KeyValueLabelsField


def test_allow_none_as_empty_dict():
    class Model(BaseModel):
        labels: KeyValueLabelsField

    assert Model(labels=None).labels == {}  # type: ignore
