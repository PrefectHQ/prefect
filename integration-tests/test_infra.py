class MyInfra:
    def __init__(self, flow, flow_run, name, run_id):
        self.flow = flow
        self.flow_run = flow_run
        self.name = name
        self.run_id = run_id

    def get_infrastructure_name(self):
        flow_name = getattr(self.flow, "name", "unknown-flow")
        flow_run_id = getattr(self.flow_run, "id", "no-flowrun")
        return f"{flow_name}-{flow_run_id}-{self.name}-{self.run_id}"

class MockFlow:
    name = "mock-flow"

class MockFlowRun:
    id = "mock-flowrun-id"

def test_infra_name_contains_flow_and_run():
    infra = MyInfra(flow=MockFlow(), flow_run=MockFlowRun(), name="xyz", run_id="abc123")
    name = infra.get_infrastructure_name()
    assert "xyz-abc123" in name
    assert MockFlow.name in name
    assert MockFlowRun.id in name
