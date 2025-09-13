from __future__ import annotations

import json
from typing import Any, List, Union
from uuid import UUID

from pydantic import TypeAdapter

from prefect._experimental.sla.objects import SlaTypes
from prefect.client.base import ServerType
from prefect.client.orchestration import PrefectClient

SlaAdapter: TypeAdapter[SlaTypes] = TypeAdapter(SlaTypes)


def _gather_deployment_sla_definitions(
    sla_flags: Union[list[str], None], existing_slas: Union[list[dict[str, Any]], None]
) -> Union[list[dict[str, Any]], None]:
    if sla_flags is not None:
        sla_specs: list[dict[str, Any]] = []
        for s in sla_flags:
            try:
                if s.endswith(".yaml"):
                    import yaml

                    with open(s, "r") as f:
                        sla_specs.extend(yaml.safe_load(f).get("sla", []))
                elif s.endswith(".json"):
                    with open(s, "r") as f:
                        sla_specs.extend(json.load(f).get("sla", []))
                else:
                    sla_specs.append(json.loads(s))
            except Exception as e:
                raise ValueError(f"Failed to parse SLA: {s}. Error: {str(e)}")
        return sla_specs

    return existing_slas


def _initialize_deployment_slas(
    deployment_id: UUID, sla_specs: list[dict[str, Any]]
) -> list[SlaTypes]:
    if sla_specs == [] or sla_specs == [[]]:
        return []

    slas = [SlaAdapter.validate_python(spec) for spec in sla_specs]
    for sla in slas:
        sla.set_deployment_id(deployment_id)
    return slas


async def _create_slas(
    client: PrefectClient,
    deployment_id: UUID,
    slas: List[SlaTypes],
):
    if client.server_type == ServerType.CLOUD:
        await client.apply_slas_for_deployment(deployment_id, slas)
    else:
        raise ValueError(
            "SLA configuration is currently only supported on Prefect Cloud."
        )
