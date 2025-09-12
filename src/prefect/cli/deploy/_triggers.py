from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter

from prefect.client.orchestration import PrefectClient
from prefect.events import DeploymentTriggerTypes, TriggerTypes
from prefect.exceptions import PrefectHTTPStatusError

DeploymentTriggerAdapter: TypeAdapter[DeploymentTriggerTypes] = TypeAdapter(
    DeploymentTriggerTypes
)


def _initialize_deployment_triggers(
    deployment_name: str, triggers_spec: list[dict[str, Any]]
) -> list[DeploymentTriggerTypes]:
    triggers: list[DeploymentTriggerTypes] = []
    for i, spec in enumerate(triggers_spec, start=1):
        spec.setdefault("name", f"{deployment_name}__automation_{i}")
        triggers.append(DeploymentTriggerAdapter.validate_python(spec))
    return triggers


async def _create_deployment_triggers(
    client: PrefectClient,
    deployment_id: UUID,
    triggers: list[DeploymentTriggerTypes | TriggerTypes],
):
    try:
        await client.delete_resource_owned_automations(
            f"prefect.deployment.{deployment_id}"
        )
    except PrefectHTTPStatusError as e:
        if e.response.status_code == 404:
            return
        raise e

    for trigger in triggers:
        trigger.set_deployment_id(deployment_id)
        await client.create_automation(trigger.as_automation())


def _gather_deployment_trigger_definitions(
    trigger_flags: list[str], existing_triggers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if trigger_flags:
        trigger_specs: list[dict[str, Any]] = []
        for t in trigger_flags:
            try:
                if t.endswith(".yaml"):
                    import yaml

                    with open(t, "r") as f:
                        trigger_specs.extend(yaml.safe_load(f).get("triggers", []))
                elif t.endswith(".json"):
                    with open(t, "r") as f:
                        trigger_specs.extend(json.load(f).get("triggers", []))
                else:
                    trigger_specs.append(json.loads(t))
            except Exception as e:
                raise ValueError(f"Failed to parse trigger: {t}. Error: {str(e)}")
        return trigger_specs

    return existing_triggers
