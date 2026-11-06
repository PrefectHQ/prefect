"""Parsing and validation of the `/run` lifecycle hook request."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

SUPPORTED_PAYLOAD_VERSION = 1
MAX_RUN_HOOK_PAYLOAD_BYTES = 16 * 1024


class InvalidRunHookPayload(ValueError):
    """Raised when a `/run` request cannot start a flow run."""


class RunHookPayload(BaseModel):
    """
    The flow run to execute, as sent in the `runHookPayload` of a `/run` hook.

    Attributes:
        v: The major version of the payload format.
        flow_run_id: The ID of the flow run to execute.
        env: Environment variables to set before the flow run starts.
        entrypoint: A flow entrypoint such as `flows/etl.py:etl`. When set, the
            flow is loaded from this entrypoint instead of from the deployment.
        working_dir: The directory to run the flow from when `entrypoint` is set.
    """

    model_config = ConfigDict(extra="ignore")

    v: int
    flow_run_id: UUID
    env: dict[str, str] = {}
    entrypoint: str | None = None
    working_dir: str | None = None


class RunHookRequest(BaseModel):
    """
    The body of a `/run` lifecycle hook request.

    Attributes:
        microvm_id: The ID of the MicroVM that received the request.
        payload: The parsed `runHookPayload`.
    """

    microvm_id: str | None
    payload: RunHookPayload


def parse_run_hook_request(body: bytes) -> RunHookRequest:
    """
    Parse the body of a `/run` lifecycle hook request.

    Args:
        body: The raw request body, a JSON object with `microvmId` and
            `runHookPayload`, where `runHookPayload` is a JSON-encoded string.

    Returns:
        The MicroVM ID and the validated payload.

    Raises:
        InvalidRunHookPayload: If the body or payload is malformed, larger than
            `MAX_RUN_HOOK_PAYLOAD_BYTES`, or has an unsupported major version.
    """
    try:
        request: Any = json.loads(body)
    except ValueError as exc:
        raise InvalidRunHookPayload(f"Request body is not JSON: {exc}") from exc
    if not isinstance(request, dict):
        raise InvalidRunHookPayload("Request body is not a JSON object.")

    raw_payload = request.get("runHookPayload")
    if not isinstance(raw_payload, str):
        raise InvalidRunHookPayload("Request body has no `runHookPayload` string.")
    payload_size = len(raw_payload.encode())
    if payload_size > MAX_RUN_HOOK_PAYLOAD_BYTES:
        raise InvalidRunHookPayload(
            f"`runHookPayload` is {payload_size} bytes; the limit is"
            f" {MAX_RUN_HOOK_PAYLOAD_BYTES}."
        )

    try:
        payload_fields: Any = json.loads(raw_payload)
    except ValueError as exc:
        raise InvalidRunHookPayload(f"`runHookPayload` is not JSON: {exc}") from exc
    if not isinstance(payload_fields, dict):
        raise InvalidRunHookPayload("`runHookPayload` is not a JSON object.")

    # Checked first, so a payload in a newer format is reported as a version
    # mismatch.
    version = payload_fields.get("v")
    if type(version) is not int or version != SUPPORTED_PAYLOAD_VERSION:
        raise InvalidRunHookPayload(
            f"Unsupported `runHookPayload` version {version!r}; this image supports"
            f" version {SUPPORTED_PAYLOAD_VERSION}."
        )

    try:
        payload = RunHookPayload.model_validate(payload_fields)
    except ValidationError as exc:
        # Input values are left out because `env` holds credentials.
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
        raise InvalidRunHookPayload(f"Invalid `runHookPayload`: {problems}") from None

    microvm_id = request.get("microvmId")
    return RunHookRequest(
        microvm_id=microvm_id if isinstance(microvm_id, str) else None,
        payload=payload,
    )
