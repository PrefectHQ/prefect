import sys
import types

import pytest

from prefect import Flow
from prefect.storage import Module


@pytest.fixture
def mymodule(monkeypatch):
    mod_name = "mymodule"
    module = types.ModuleType(mod_name)
    monkeypatch.setitem(sys.modules, mod_name, module)
    return module


class TestModule:
    def test_init(self):
        storage = Module("mymodule")
        assert storage.module == "mymodule"

    def test_add_flow(self):
        flow = Flow("test")

        storage = Module("mymodule")
        assert flow.name not in storage

        storage.add_flow(flow)
        assert flow.name in storage

        with pytest.raises(ValueError, match="Name conflict"):
            storage.add_flow(flow)

    def test_get_flow(self, mymodule):
        flow = Flow("test")
        mymodule.flow = flow

        storage = Module("mymodule")
        storage.add_flow(flow)

        flow2 = storage.get_flow(flow.name)
        assert flow2 is flow

    def test_get_flow_name_mismatch(self, mymodule):
        flow = Flow("test")
        mymodule.flow = Flow("other name")

        storage = Module("mymodule")
        storage.add_flow(flow)

        with pytest.raises(ValueError, match="Failed to find flow"):
            storage.get_flow(flow.name)
