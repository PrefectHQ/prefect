from typing import List

import httpx
import pytest
from prefect_databricks import DatabricksCredentials
from prefect_databricks.rest import (
    HTTPMethod,
    execute_endpoint,
    serialize_model,
    strip_kwargs,
)
from pydantic import BaseModel, Extra


@pytest.mark.parametrize("params", [dict(a="A", b="B"), None])
@pytest.mark.parametrize("http_method", ["get", HTTPMethod.GET, "post"])
async def test_execute_endpoint(params, http_method, respx_mock):
    url = "https://prefect.io/"

    respx_mock.get(url).mock(return_value=httpx.Response(200))
    respx_mock.post(url).mock(return_value=httpx.Response(200))

    execute_kwargs = dict()
    if http_method == "post":
        execute_kwargs["json"] = {"key": "val"}

    credentials = DatabricksCredentials(
        databricks_instance="databricks_instance",
        token="token_value",
    )
    response = await execute_endpoint.fn(
        url, credentials, http_method=http_method, params=params, **execute_kwargs
    )
    assert response.status_code == 200


def test_strip_kwargs():
    assert strip_kwargs(**{"a": None, "b": None}) == {}
    assert strip_kwargs(**{"a": "", "b": None}) == {"a": ""}
    assert strip_kwargs(**{"a": "abc", "b": "def"}) == {"a": "abc", "b": "def"}
    assert strip_kwargs(a="abc", b="def") == {"a": "abc", "b": "def"}
    assert strip_kwargs(**dict(a=[])) == {"a": []}


class TestAnotherBaseModel(BaseModel):
    some_float: float
    some_bool: bool


class TestBaseModel(BaseModel):
    class Config:
        extra = Extra.allow
        allow_mutation = False

    some_string: str
    some_int: int
    another_base_model: TestAnotherBaseModel
    other_base_models: List[TestAnotherBaseModel]


def test_serialize_model():
    expected = {
        "base_model": {
            "some_string": "abc",
            "some_int": 1,
            "another_base_model": {"some_float": 2.8, "some_bool": True},
            "other_base_models": [
                {"some_float": 8.8, "some_bool": False},
                {"some_float": 1.8, "some_bool": True},
            ],
            "unexpected_value": ["super", "unexpected"],
        }
    }

    actual = serialize_model(
        {
            "base_model": TestBaseModel(
                some_string="abc",
                some_int=1,
                unexpected_value=["super", "unexpected"],
                another_base_model=TestAnotherBaseModel(some_float=2.8, some_bool=True),
                other_base_models=[
                    TestAnotherBaseModel(some_float=8.8, some_bool=False),
                    TestAnotherBaseModel(some_float=1.8, some_bool=True),
                ],
            )
        }
    )

    assert expected == actual
