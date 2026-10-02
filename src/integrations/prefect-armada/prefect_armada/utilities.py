"""Utilities for working with the Armada Python client."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from armada_client.armada import submit_pb2
from armada_client.k8s.io.api.core.v1 import generated_pb2 as core_v1
from armada_client.typings import JobState
from google.protobuf import json_format
from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message
from slugify import slugify

from prefect_armada.exceptions import ArmadaJobDefinitionError

# Armada job states that a job will never transition out of.
TERMINAL_JOB_STATES: set[JobState] = {
    JobState.SUCCEEDED,
    JobState.FAILED,
    JobState.PREEMPTED,
    JobState.CANCELLED,
    JobState.REJECTED,
}

# Terminal Armada job states that indicate the job did not run to completion.
UNSUCCESSFUL_JOB_STATES: set[JobState] = TERMINAL_JOB_STATES - {JobState.SUCCEEDED}

# Armada event types that indicate a job will never produce a result. Armada
# does not emit a "rejected" event type; rejections surface as failures.
UNSUCCESSFUL_EVENT_TYPES: set[str] = {
    "failed",
    "cancelled",
    "preempted",
    "lease_expired",
}

# The annotation key prefix Armada uses for job metadata that is meaningful to
# systems outside of Armada.
ARMADA_ANNOTATION_PREFIX = "armadaproject.io/"


def _grpc_keepalive_options() -> list[tuple[str, Any]]:
    """Returns gRPC channel options that enable TCP keepalive.

    Long-lived Armada event streams are frequently held open through load
    balancers and NAT gateways that silently drop idle connections. gRPC will
    not notice the dropped connection without keepalive pings, so a stream can
    hang indefinitely instead of reconnecting.

    Returns:
        A list of gRPC channel option tuples.
    """
    return [
        ("grpc.keepalive_time_ms", 30000),
        ("grpc.keepalive_timeout_ms", 10000),
        ("grpc.keepalive_permit_without_calls", 1),
        ("grpc.http2.max_pings_without_data", 0),
    ]


def _slugify_name(name: str, max_length: int = 45) -> str | None:
    """
    Slugify text for use as a name.

    Keeps only alphanumeric characters and dashes, and caps the length
    of the slug at 45 chars.

    The 45 character length keeps the total length of a name below 63
    characters, which is the limit for names such as labels that follow
    RFC 1123 (hostnames) and RFC 1035 (domain names).

    Args:
        name: The name of the job

    Returns:
        The slugified job name or None if the slugified name is empty
    """
    slug = slugify(
        name,
        max_length=max_length,
        regex_pattern=r"[^a-zA-Z0-9-]+",
    )

    return slug if slug else None


def _slugify_label_key(key: str, max_length: int = 63, prefix_max_length=253) -> str:
    """
    Slugify text for use as a label or annotation key.

    Keys are composed of an optional prefix and name, separated by a slash (/).

    Keeps only alphanumeric characters, dashes, underscores, and periods.
    Limits the length of the label prefix to 253 characters.
    Limits the length of the label name to 63 characters.

    See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set

    Args:
        key: The label key

    Returns:
        The slugified label key
    """
    if "/" in key:
        prefix, name = key.split("/", maxsplit=1)
    else:
        prefix = None
        name = key

    name_slug = (
        slugify(
            name,
            lowercase=False,
            max_length=max_length,
            regex_pattern=r"[^a-zA-Z0-9-_.]+",
        ).strip(
            "_-."  # Must start or end with alphanumeric characters
        )
        or name
    )
    # Fallback to the original if we end up with an empty slug, this will allow
    # Armada and Kubernetes to throw the validation error

    if prefix:
        prefix_slug = (
            slugify(
                prefix,
                lowercase=False,
                max_length=prefix_max_length,
                regex_pattern=r"[^a-zA-Z0-9-\.]+",
            ).strip("_-.")  # Must start or end with alphanumeric characters
            or prefix
        )

        return f"{prefix_slug}/{name_slug}"

    return name_slug


def _slugify_label_value(value: str, max_length: int = 63) -> str:
    """
    Slugify text for use as a label value.

    Keeps only alphanumeric characters, dashes, underscores, and periods.
    Limits the total length of label text to below 63 characters.

    See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set

    Args:
        value: The text for the label

    Returns:
        The slugified value
    """
    slug = (
        slugify(
            value,
            lowercase=False,
            max_length=max_length,
            regex_pattern=r"[^a-zA-Z0-9-_\.]+",
        ).strip(
            "_-."  # Must start or end with alphanumeric characters
        )
        or value
    )
    # Fallback to the original if we end up with an empty slug, this will allow
    # Armada and Kubernetes to throw the validation error

    return slug


def _field_by_name(descriptor: Descriptor, key: str) -> FieldDescriptor | None:
    """Looks up a protobuf field by either its proto name or its JSON name."""
    field = descriptor.fields_by_name.get(key)
    if field is not None:
        return field
    return next((f for f in descriptor.fields if f.json_name == key), None)


def _is_repeated(field: FieldDescriptor) -> bool:
    """Returns whether a protobuf field is repeated."""
    # `FieldDescriptor.label` is deprecated in protobuf 6 in favor of
    # `is_repeated`, which older versions do not have.
    is_repeated = getattr(field, "is_repeated", None)
    if is_repeated is not None:
        return bool(is_repeated)
    return field.label == FieldDescriptor.LABEL_REPEATED


def _normalize_message_dict(value: Any, descriptor: Descriptor) -> Any:
    """Prepares a plain dictionary for parsing into a protobuf message.

    Armada consumes Kubernetes pod specs as protobuf messages rather than the
    JSON that Kubernetes itself accepts, and two differences make a manifest
    written by hand unusable as-is:

    - Resource quantities (for example `"500m"`) are `Quantity` messages with a
      single `string` field, so `{"cpu": "500m"}` must become
      `{"cpu": {"string": "500m"}}`.
    - `None` values are not valid for any protobuf field, and they show up
      routinely after job template rendering when an optional work pool
      variable has not been set.

    Args:
        value: The value to normalize.
        descriptor: The descriptor of the message `value` should conform to.

    Returns:
        A dictionary suitable for `google.protobuf.json_format.ParseDict`.
    """
    if descriptor.full_name.endswith("api.resource.Quantity") and not isinstance(
        value, dict
    ):
        return {"string": str(value)}

    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if item is None:
            continue
        field = _field_by_name(descriptor, key)
        if field is None:
            # Leave unknown keys in place so `ParseDict` raises an error that
            # names the offending field.
            normalized[key] = item
            continue
        normalized[field.json_name] = _normalize_field(field, item)
    return normalized


def _normalize_field(field: FieldDescriptor, value: Any) -> Any:
    """Normalizes a single field value for parsing into a protobuf message."""
    if field.message_type is None:
        return value

    message_type = field.message_type
    if message_type.GetOptions().map_entry:
        value_field = message_type.fields_by_name["value"]
        return {
            key: _normalize_field(value_field, item)
            for key, item in value.items()
            if item is not None
        }

    if _is_repeated(field):
        return [
            _normalize_message_dict(item, message_type)
            for item in value
            if item is not None
        ]

    return _normalize_message_dict(value, message_type)


def _parse_into(value: dict[str, Any], message: Message) -> Message:
    """Parses a plain dictionary into the given protobuf message."""
    try:
        return json_format.ParseDict(
            _normalize_message_dict(value, message.DESCRIPTOR), message
        )
    except json_format.Error as exc:
        raise ArmadaJobDefinitionError(str(exc)) from exc


def pod_spec_from_dict(pod_spec: dict[str, Any]) -> core_v1.PodSpec:
    """Converts a Kubernetes pod spec dictionary into an Armada pod spec.

    Args:
        pod_spec: A Kubernetes pod spec, for example one produced by
            `yaml.safe_load`.

    Returns:
        The equivalent `PodSpec` protobuf message.

    Raises:
        ArmadaJobDefinitionError: If the pod spec cannot be converted.

    Example:
        ```python
        from prefect_armada.utilities import pod_spec_from_dict

        pod_spec = pod_spec_from_dict(
            {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "prefect-job",
                        "image": "prefecthq/prefect:3-latest",
                        "resources": {"requests": {"cpu": "500m"}},
                    }
                ],
            }
        )
        ```
    """
    return _parse_into(pod_spec, core_v1.PodSpec())


def job_request_item_from_dict(
    job_request: dict[str, Any],
) -> submit_pb2.JobSubmitRequestItem:
    """Converts a job request dictionary into an Armada job submit request item.

    Args:
        job_request: An Armada `JobSubmitRequestItem` in dictionary form. Nested
            pod specs may be given under either `pod_spec` or `podSpec`.

    Returns:
        The equivalent `JobSubmitRequestItem` protobuf message.

    Raises:
        ArmadaJobDefinitionError: If the job request cannot be converted.

    Example:
        ```python
        from prefect_armada.utilities import job_request_item_from_dict

        job_request_item = job_request_item_from_dict(
            {
                "priority": 1,
                "namespace": "default",
                "podSpec": {
                    "containers": [
                        {"name": "prefect-job", "image": "prefecthq/prefect:3-latest"}
                    ]
                },
            }
        )
        ```
    """
    return _parse_into(job_request, submit_pb2.JobSubmitRequestItem())


def coerce_job_request_items(
    job_request: dict[str, Any]
    | submit_pb2.JobSubmitRequestItem
    | list[dict[str, Any] | submit_pb2.JobSubmitRequestItem],
) -> list[submit_pb2.JobSubmitRequestItem]:
    """Coerces job request input into a list of job submit request items.

    Accepts a single job request or a list of job requests, in either
    dictionary or protobuf form, so that tasks and blocks can be given whatever
    representation is most convenient.

    Args:
        job_request: The job request(s) to coerce.

    Returns:
        A list of `JobSubmitRequestItem` protobuf messages.

    Raises:
        ArmadaJobDefinitionError: If a job request cannot be converted.
    """
    items = job_request if isinstance(job_request, list) else [job_request]
    return [
        item
        if isinstance(item, submit_pb2.JobSubmitRequestItem)
        else job_request_item_from_dict(item)
        for item in items
    ]


def queue_from_dict(queue: dict[str, Any]) -> submit_pb2.Queue:
    """Converts a queue dictionary into an Armada queue.

    Args:
        queue: An Armada `Queue` in dictionary form.

    Returns:
        The equivalent `Queue` protobuf message.

    Raises:
        ArmadaJobDefinitionError: If the queue cannot be converted.
    """
    return _parse_into(queue, submit_pb2.Queue())


def coerce_queues(
    queues: Iterable[dict[str, Any] | submit_pb2.Queue],
) -> list[submit_pb2.Queue]:
    """Coerces queue input into a list of Armada queues.

    Args:
        queues: Queues given in dictionary or protobuf form.

    Returns:
        A list of `Queue` protobuf messages.

    Raises:
        ArmadaJobDefinitionError: If a queue cannot be converted.
    """
    return [
        queue if isinstance(queue, submit_pb2.Queue) else queue_from_dict(queue)
        for queue in queues
    ]


def job_state_from_value(value: Any) -> JobState:
    """Converts an Armada job state value into a `JobState`.

    Args:
        value: A `JobState` enum member, its integer value, or its name.

    Returns:
        The corresponding `JobState`.

    Raises:
        ValueError: If the value does not correspond to a known job state.
    """
    if isinstance(value, JobState):
        return value
    if isinstance(value, str):
        return JobState[value.upper()]
    return JobState(value)


def format_job_pid(queue: str, job_set_id: str, job_id: str) -> str:
    """Formats an Armada job identifier for use as an infrastructure PID.

    Args:
        queue: The name of the Armada queue.
        job_set_id: The name of the Armada job set.
        job_id: The Armada job ID.

    Returns:
        The infrastructure PID, for example `"my-queue:my-job-set:01hqk..."`.
    """
    return f"{queue}:{job_set_id}:{job_id}"


def parse_job_pid(infrastructure_pid: str) -> tuple[str, str, str]:
    """Parses an infrastructure PID into its Armada job identifiers.

    Args:
        infrastructure_pid: An identifier in the format
            `"<queue>:<job_set_id>:<job_id>"`.

    Returns:
        A tuple of `(queue, job_set_id, job_id)`.

    Raises:
        ValueError: If the identifier is not in the expected format.
    """
    parts = infrastructure_pid.split(":")
    if len(parts) != 3 or not all(parts):
        raise ValueError(
            f"Invalid infrastructure_pid format: {infrastructure_pid!r}. "
            "Expected format: '<queue>:<job_set_id>:<job_id>'"
        )
    queue, job_set_id, job_id = parts
    return queue, job_set_id, job_id
