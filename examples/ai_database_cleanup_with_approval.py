# ---
# title: Database Cleanup with Human or AI Approval
# description: Build database cleanup workflows that evolve from human oversight to AI autonomy.
# icon: database
# keywords: ["ai", "agents", "pydantic-ai", "database-maintenance", "cleanup", "automation", "approval-workflow", "mcp"]
# github_url: https://github.com/zzstoatzz/prefect-mcp-server-demo
# order: 7
# ---
#
# Database cleanup is critical for self-hosted Prefect deployments (see [database maintenance guide](/v3/advanced/database-maintenance)),
# but it's risky: too automated and you might delete important data, too manual and it becomes a constant burden.
#
# This example shows how to build a cleanup workflow that evolves with your confidence:
#
# - **Start with human approval**: Preview what will be deleted, pause the flow, and manually approve/reject via a UI form
# - **Graduate to AI autonomy**: Switch to an AI agent that investigates system health using Prefect MCP tools and returns structured decisions with confidence scores
#
# Build trust incrementally by monitoring decisions in lower-risk environments before enabling AI autonomy in production.
#
# For a full deployment example with scheduling and environment configuration, see:
# [github.com/zzstoatzz/prefect-mcp-server-demo](https://github.com/zzstoatzz/prefect-mcp-server-demo)
#
# ## Setup
#
# ```bash
# # For human approval only
# uv add prefect
#
# # For AI approval, add pydantic-ai
# uv add 'pydantic-ai[prefect]'
# export ANTHROPIC_API_KEY='your-key'
# ```
#
# The Prefect MCP server provides AI agents with read-only tools for investigating your Prefect instance.
# See [How to use the Prefect MCP server](/v3/how-to-guides/ai/use-prefect-mcp-server) for setup.

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.durable_exec.prefect import PrefectAgent, TaskConfig
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai_mcp import MCPServerStdio

from prefect import flow, get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterStartTime,
    FlowRunFilterStateName,
)
from prefect.exceptions import ObjectNotFound
from prefect.flow_runs import pause_flow_run
from prefect.input import RunInput

# ## Configuration: Make Cleanup Policy Explicit
#
# Instead of scattering configuration across your code, define it as a structured Pydantic model.
# This becomes a UI form automatically - see [form building guide](/v3/advanced/form-building).


class RetentionConfig(BaseModel):
    """Define what to clean and how."""

    retention_period: timedelta = Field(
        default=timedelta(days=30), description="How far back to keep flow runs"
    )
    states_to_clean: list[str] = Field(
        default=["Completed", "Failed", "Cancelled"],
        description="Which states to clean",
    )
    batch_size: int = Field(default=100, ge=10, le=1000)
    dry_run: bool = Field(default=False, description="Preview without deleting")
    approval_type: Literal["human", "ai"] = Field(
        default="human", description="Human form or AI agent approval"
    )


# <AccordionGroup>
#
# <Accordion title="Human Approval: Pause and Review">
#
# When using `approval_type="human"`, the flow pauses and shows a form in the UI.


class CleanupApproval(RunInput):
    """Human approval form for cleanup operations."""

    approve: bool = Field(default=False)
    notes: str = Field(default="", description="Why approve/reject?")


@flow(name="human-approval")
def get_human_approval(preview: str, count: int) -> tuple[bool, str]:
    """Pause and wait for human decision via UI form."""
    print(f"⏸️  pausing for human review of {count} flow runs...")

    approval = pause_flow_run(
        wait_for_input=CleanupApproval.with_initial_data(
            description=f"**Preview ({count} runs):**\n{preview}"
        ),
        timeout=3600,
    )

    return approval.approve, approval.notes


# </Accordion>
#
# <Accordion title="AI Approval: Autonomous Investigation">
#
# When using `approval_type="ai"`, a pydantic-ai agent investigates using Prefect MCP tools to decide if cleanup is safe.

AGENT_PROMPT = """you are a prefect infrastructure operations agent reviewing a proposed database cleanup.

use the prefect mcp tools to investigate system health:
- query recent flow run patterns
- check deployment schedules
- review system status

return your decision with confidence (0-1), reasoning, and any concerns.

approve routine cleanup unless you detect risks like ongoing incidents or critical deployments needing history."""


class CleanupDecision(BaseModel):
    """Structured AI decision."""

    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    concerns: list[str] | None = None


def create_cleanup_agent() -> PrefectAgent[None, CleanupDecision]:
    """Create AI agent with Prefect MCP tools for autonomous approval."""
    # Connect to Prefect MCP server - provides read-only Prefect tools
    mcp_server = MCPServerStdio(
        "prefect", "uvx", args=["--from", "prefect-mcp", "prefect-mcp-server"]
    )

    agent = Agent(
        model=AnthropicModel("claude-sonnet-4-5-20250929"),
        output_type=CleanupDecision,
        system_prompt=AGENT_PROMPT,
        mcp_servers=[mcp_server],
    )

    # Wrap with PrefectAgent for retry/timeout handling
    return PrefectAgent(
        agent,
        model_task_config=TaskConfig(retries=2, timeout_seconds=120.0),
    )


@flow(name="ai-approval", log_prints=True)
async def get_ai_approval(
    preview: str, count: int, config: RetentionConfig
) -> tuple[bool, str]:
    """Use AI agent to autonomously decide approval."""
    print("🤖 requesting ai agent decision...")

    agent = create_cleanup_agent()

    context = f"""
proposed cleanup:
- retention: {config.retention_period}
- states: {", ".join(config.states_to_clean)}
- count: {count} flow runs

preview:
{preview}

investigate using your prefect mcp tools and decide if safe to proceed.
"""

    result = await agent.run(context)
    decision = result.output

    print(f"decision: {'✅ approved' if decision.approved else '❌ rejected'}")
    print(f"confidence: {decision.confidence:.0%}")
    print(f"reasoning: {decision.reasoning}")

    return decision.approved, decision.reasoning


# </Accordion>
#
# <Accordion title="Main Cleanup Flow">


@flow(name="database-cleanup", log_prints=True)
async def database_cleanup_flow(config: RetentionConfig | None = None) -> dict:
    """Database cleanup with configurable approval workflow."""
    if config is None:
        config = RetentionConfig()

    print(f"🚀 starting cleanup (approval: {config.approval_type})")

    # Fetch flow runs matching retention policy
    async with get_client() as client:
        cutoff = datetime.now(timezone.utc) - config.retention_period
        flow_runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                start_time=FlowRunFilterStartTime(before_=cutoff),
                state=FlowRunFilterStateName(any_=config.states_to_clean),
            ),
            limit=config.batch_size * 5,
        )

    if not flow_runs:
        print("✨ nothing to clean")
        return {"status": "no_action", "deleted": 0}

    # Preview what will be deleted
    preview = "\n".join(
        f"- {r.name} ({r.state.type.value}) - {r.start_time}" for r in flow_runs[:5]
    )
    if len(flow_runs) > 5:
        preview += f"\n... and {len(flow_runs) - 5} more"

    print(f"\n📋 preview:\n{preview}\n")

    # Get approval (human or AI based on config)
    if config.approval_type == "human":
        approved, notes = get_human_approval(preview, len(flow_runs))
    else:
        approved, notes = await get_ai_approval(preview, len(flow_runs), config)

    if not approved:
        print(f"❌ cleanup rejected: {notes}")
        return {"status": "rejected", "reason": notes}

    print(f"✅ cleanup approved: {notes}")

    if config.dry_run:
        print("🔍 dry run - no deletions")
        return {"status": "dry_run", "would_delete": len(flow_runs)}

    # Perform deletion with batching and rate limiting
    deleted = 0
    async with get_client() as client:
        for i in range(0, len(flow_runs), config.batch_size):
            batch = flow_runs[i : i + config.batch_size]
            for run in batch:
                try:
                    await client.delete_flow_run(run.id)
                    deleted += 1
                except ObjectNotFound:
                    # Already deleted (e.g., by concurrent cleanup) - treat as success
                    deleted += 1
                except Exception as e:
                    print(f"failed to delete {run.id}: {e}")
                await asyncio.sleep(0.1)  # rate limiting

    print(f"✅ deleted {deleted}/{len(flow_runs)} flow runs")
    return {"status": "completed", "deleted": deleted}


# </Accordion>
#
# </AccordionGroup>
#
# ## Deployment Examples

if __name__ == "__main__":
    # Start with human approval in production
    prod_config = RetentionConfig(
        retention_period=timedelta(days=30),
        dry_run=False,
        approval_type="human",
    )

    # Graduate to AI approval in dev/staging
    dev_config = RetentionConfig(
        retention_period=timedelta(minutes=5),
        dry_run=False,
        approval_type="ai",  # requires ANTHROPIC_API_KEY
    )

    database_cleanup_flow.serve(
        name="database-cleanup-deployment",
        tags=["database-maintenance", "cleanup"],
    )

# ## Related Documentation
#
# - [Database Maintenance Guide](/v3/advanced/database-maintenance) - SQL queries, retention strategies, VACUUM
# - [Form Building](/v3/advanced/form-building) - Create validated UI forms from Pydantic models
# - [Interactive Workflows](/v3/advanced/interactive) - Pause flows and wait for human input
# - [Prefect MCP Server](/v3/how-to-guides/ai/use-prefect-mcp-server) - Connect AI agents to Prefect
# - [pydantic-ai + Prefect](https://ai.pydantic.dev/durable_execution/prefect/) - Durable AI agents with retries
