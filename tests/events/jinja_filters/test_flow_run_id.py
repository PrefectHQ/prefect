from prefect.server.events.jinja_filters import flow_run_id


def test_flow_run_id_extraction():
    url = "https://app.prefect.cloud/account/abc/workspace/xyz/runs/flow-run/12345678-1234-5678-1234-567812345678"
    body = f"Fixes {url}"
    assert flow_run_id(body) == "12345678-1234-5678-1234-567812345678"


def test_flow_run_id_extraction_no_match():
    body = "Fixes something else"
    assert flow_run_id(body) is None


def test_flow_run_id_extraction_none():
    assert flow_run_id(None) is None
