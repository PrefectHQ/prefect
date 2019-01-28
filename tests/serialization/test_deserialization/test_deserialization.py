import json
import os

import pytest

import prefect
from prefect import serialization as s

file_dir = os.path.dirname(__file__)


@pytest.fixture
def version_0_3_0():
    with open(os.path.join(file_dir, "version_0_3_0.json")) as f:
        return json.load(f)


@pytest.fixture
def version_0_4_0():
    with open(os.path.join(file_dir, "version_0_4_0.json")) as f:
        return json.load(f)


class Test_Version_0_3_0:
    def test_deserialize_success(self, version_0_3_0):
        state = s.state.StateSchema().load(version_0_3_0["states"]["success"])
        assert state.is_successful()

    def test_deserialize_retrying(self, version_0_3_0):
        state = s.state.StateSchema().load(version_0_3_0["states"]["retrying"])
        assert isinstance(state, prefect.engine.state.Retrying)


class Test_Version_0_4_0:
    def test_deserialize_success(self, version_0_4_0):
        state = s.state.StateSchema().load(version_0_4_0["states"]["success"])
        assert state.is_successful()

    def test_deserialize_retrying(self, version_0_4_0):
        state = s.state.StateSchema().load(version_0_4_0["states"]["retrying"])
        assert isinstance(state, prefect.engine.state.Retrying)
