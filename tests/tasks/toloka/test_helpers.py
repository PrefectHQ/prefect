import functools
import json
import pytest
import requests_mock
from prefect.tasks.toloka.helpers import download_json


URL = "https://some.url"
CONTENT = {"key": ["value", "значение", "価値"]}


_json_dump = functools.partial(json.dumps, ensure_ascii=False)


@pytest.fixture
def mocked_url():
    with requests_mock.Mocker(real_http=False) as mock:
        mock.get(URL, content=_json_dump(CONTENT).encode())
        yield URL


def test_download_json(mocked_url):
    assert CONTENT == download_json.run(mocked_url)
