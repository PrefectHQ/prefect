def test_infra_name_contains_flow_and_run():
    infra = MyInfra(flow=my_flow_obj, flow_run=my_flow_run_obj, name="xyz", run_id="abc123")
    name = infra.get_infrastructure_name()
    assert "xyz-abc123" in name
    assert my_flow_obj.name in name
    assert my_flow_run_obj.id in name
