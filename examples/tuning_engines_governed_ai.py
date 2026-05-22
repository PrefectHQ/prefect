# ---
# title: Governed AI with Tuning Engines
# description: Route model calls through Tuning Engines while Prefect owns retries, schedules, and flow observability.
# icon: robot
# dependencies: ["prefect", "httpx"]
# keywords: ["ai", "llm", "governance", "orchestration"]
# draft: false
# order: 10
# ---
#
# This example shows how to call Tuning Engines from a Prefect task. Prefect
# owns the flow run, retries, schedules, and deployment lifecycle. Tuning
# Engines owns model routing, policy checks, approval decisions, usage
# attribution, and gateway traces.
#
# ## Setup
#
# ```bash
# uv add prefect httpx
# export TE_INFERENCE_KEY=sk-te-your-inference-key
# export TE_MODEL=auto
# ```

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx

from prefect import flow, task


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@task(retries=2, retry_delay_seconds=5)
def governed_model_call(prompt: str, run_id: str) -> dict[str, Any]:
    """Call Tuning Engines from a durable Prefect task."""
    request_id = new_id("req")
    api_key = os.environ["TE_INFERENCE_KEY"]
    response = httpx.post(
        "https://api.tuningengines.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-TE-Run-ID": run_id,
            "X-TE-Request-ID": request_id,
        },
        timeout=60,
        json={
            "model": os.getenv("TE_MODEL", "auto"),
            "messages": [{"role": "user", "content": prompt}],
            "metadata": {
                "run_id": run_id,
                "request_id": request_id,
                "runtime": "prefect",
                "event_type": "model.call",
            },
        },
    )
    response.raise_for_status()
    return response.json()


@flow(name="tuning-engines-governed-ai", log_prints=True)
def governed_ai_flow(
    prompt: str = "Summarize why durable AI workflows matter.",
) -> dict[str, Any]:
    run_id = new_id("prefect")
    result = governed_model_call(prompt, run_id)
    print(f"Correlate this Prefect flow with Tuning Engines run_id={run_id}")
    return result


if __name__ == "__main__":
    governed_ai_flow()
