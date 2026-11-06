import json
from uuid import UUID

import pytest
from prefect_aws.microvm.payload import (
    MAX_RUN_HOOK_PAYLOAD_BYTES,
    InvalidRunHookPayload,
    parse_run_hook_request,
)

FLOW_RUN_ID = UUID("6c1b0d4e-5e1f-4b6a-9d0e-3f1d2c3b4a59")


def make_body(payload: object, microvm_id: str | None = "microvm-1234") -> bytes:
    raw_payload = payload if isinstance(payload, str) else json.dumps(payload)
    return json.dumps({"microvmId": microvm_id, "runHookPayload": raw_payload}).encode()


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "v": 1,
        "flow_run_id": str(FLOW_RUN_ID),
        "env": {
            "PREFECT_API_URL": "https://api.example.com/api",
            "PREFECT_API_KEY": "pnu_secret",
            "PREFECT__FLOW_RUN_ID": str(FLOW_RUN_ID),
        },
        "entrypoint": "flows/etl.py:etl",
        "working_dir": "/opt/prefect/proj",
    }
    payload.update(overrides)
    return payload


def test_parses_a_version_1_payload():
    request = parse_run_hook_request(make_body(valid_payload()))

    assert request.microvm_id == "microvm-1234"
    assert request.payload.v == 1
    assert request.payload.flow_run_id == FLOW_RUN_ID
    assert request.payload.env == {
        "PREFECT_API_URL": "https://api.example.com/api",
        "PREFECT_API_KEY": "pnu_secret",
        "PREFECT__FLOW_RUN_ID": str(FLOW_RUN_ID),
    }
    assert request.payload.entrypoint == "flows/etl.py:etl"
    assert request.payload.working_dir == "/opt/prefect/proj"


def test_null_entrypoint_and_working_dir_parse_as_none():
    request = parse_run_hook_request(
        make_body(valid_payload(entrypoint=None, working_dir=None))
    )

    assert request.payload.entrypoint is None
    assert request.payload.working_dir is None


def test_unknown_keys_are_ignored():
    request = parse_run_hook_request(
        make_body(valid_payload(future_field={"nested": True}))
    )

    assert request.payload.flow_run_id == FLOW_RUN_ID
    assert "future_field" not in request.payload.model_dump()


@pytest.mark.parametrize("version", [2, 0, "1", 1.0, True, None])
def test_rejects_versions_other_than_integer_1(version: object):
    payload = valid_payload(v=version)
    if version is None:
        del payload["v"]

    with pytest.raises(
        InvalidRunHookPayload, match="Unsupported `runHookPayload` version"
    ):
        parse_run_hook_request(make_body(payload))


def payload_of_size(size: int) -> str:
    payload = valid_payload()
    base_size = len(json.dumps({**payload, "padding": ""}).encode())
    return json.dumps({**payload, "padding": "x" * (size - base_size)})


def test_accepts_a_payload_of_exactly_16_kb():
    raw_payload = payload_of_size(MAX_RUN_HOOK_PAYLOAD_BYTES)
    assert len(raw_payload.encode()) == 16 * 1024

    request = parse_run_hook_request(make_body(raw_payload))

    assert request.payload.flow_run_id == FLOW_RUN_ID


def test_rejects_a_payload_over_16_kb():
    raw_payload = payload_of_size(MAX_RUN_HOOK_PAYLOAD_BYTES + 1)

    with pytest.raises(InvalidRunHookPayload, match="16385 bytes; the limit is 16384"):
        parse_run_hook_request(make_body(raw_payload))


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        json.dumps({"microvmId": "microvm-1234"}).encode(),
        json.dumps({"runHookPayload": {"v": 1}}).encode(),
        make_body("not json"),
        make_body("[1]"),
    ],
)
def test_rejects_malformed_bodies(body: bytes):
    with pytest.raises(InvalidRunHookPayload):
        parse_run_hook_request(body)


@pytest.mark.parametrize(
    "overrides",
    [
        {"flow_run_id": "not-a-uuid"},
        {"flow_run_id": None},
        {"env": {"PREFECT_API_KEY": "pnu_secret", "COUNT": 3}},
        {"env": ["PREFECT_API_KEY=pnu_secret"]},
    ],
)
def test_invalid_fields_are_rejected_without_echoing_the_input(
    overrides: dict[str, object],
):
    with pytest.raises(InvalidRunHookPayload) as exc_info:
        parse_run_hook_request(make_body(valid_payload(**overrides)))

    assert "pnu_secret" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__


def test_missing_microvm_id_parses_as_none():
    request = parse_run_hook_request(make_body(valid_payload(), microvm_id=None))

    assert request.microvm_id is None


def test_flow_run_id_must_be_present():
    payload = valid_payload()
    del payload["flow_run_id"]

    with pytest.raises(InvalidRunHookPayload, match="flow_run_id"):
        parse_run_hook_request(make_body(payload))


def test_env_defaults_to_empty():
    payload = valid_payload()
    del payload["env"]

    request = parse_run_hook_request(make_body(payload))

    assert request.payload.env == {}
