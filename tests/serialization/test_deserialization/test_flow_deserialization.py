import glob
import json
import os

import pytest

from prefect.serialization.flow import FlowSchema

ALL_FLOWS = glob.glob(os.path.join(os.path.dirname(__file__), "flows/") + "*.json")


@pytest.mark.parametrize("flow_json", ALL_FLOWS)
def test_old_flows_deserialize(flow_json):
    with open(flow_json, "r") as f:
        payload = json.load(f)
    flow = FlowSchema().load(payload)
    assert flow.name
