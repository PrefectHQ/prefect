# ---
# title: Transactional AI Agent with Rollback
# description: Build AI agents with automatic rollback when tools fail - the SAGA pattern for agentic workflows.
# icon: rotate-left
# dependencies: ["prefect", "pydantic-ai"]
# keywords: ["ai", "agents", "pydantic-ai", "transactions", "rollback", "saga", "mcp", "side-effects"]
# order: 8
# ---
#
# AI agents are while loops that call tools. Those tools have side effects -
# creating issues, sending messages, updating databases. But what happens when
# tool #3 fails after tools #1 and #2 already ran?
#
# MCP (Model Context Protocol) enables agents to call tools across systems,
# but it doesn't provide rollback semantics. If an agent creates a GitHub issue,
# sends a Slack notification, then fails on the database update - you're left
# with orphaned side effects.
#
# Prefect's transaction system solves this with the SAGA pattern:
# - Wrap agent tool calls in a `transaction()` context
# - Register compensating actions via `on_rollback` hooks
# - If any tool fails, all previous side effects are automatically rolled back
#
# This example demonstrates:
# * **Transactional tool execution** - Group side effects into atomic units
# * **Automatic rollback** - Compensating actions run on failure
# * **SAGA choreography** - Each tool knows how to undo itself
# * **Works with any MCP server** - The pattern applies to any tool with side effects
#
# ## Setup
#
# ```bash
# uv add prefect pydantic-ai
# export OPENAI_API_KEY='your-key'
# ```

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from prefect import flow, task
from prefect.transactions import get_transaction, transaction

# ## Simulated External Systems
#
# These represent the external services an agent might interact with.
# In production, these would be real API calls - GitHub, Slack, databases, etc.


@dataclass
class ExternalSystems:
    """External systems that an agent interacts with."""

    created_issues: list[str] = field(default_factory=list)
    sent_messages: list[str] = field(default_factory=list)
    database_records: list[dict] = field(default_factory=list)

    # Toggle to simulate failures
    fail_on_notification: bool = False

    def create_github_issue(self, title: str, body: str) -> str:
        """Create a GitHub issue - returns issue ID."""
        issue_id = f"GH-{len(self.created_issues) + 1}"
        self.created_issues.append(issue_id)
        print(f"  [GitHub] created issue {issue_id}: {title}")
        return issue_id

    def delete_github_issue(self, issue_id: str) -> None:
        """Delete a GitHub issue (compensating action)."""
        if issue_id in self.created_issues:
            self.created_issues.remove(issue_id)
            print(f"  [GitHub] ROLLBACK: deleted issue {issue_id}")

    def send_slack_message(self, channel: str, text: str) -> str:
        """Send a Slack message - returns message ID."""
        if self.fail_on_notification:
            raise RuntimeError("Slack API error: rate limited!")
        msg_id = f"MSG-{len(self.sent_messages) + 1}"
        self.sent_messages.append(msg_id)
        print(f"  [Slack] sent message {msg_id} to #{channel}")
        return msg_id

    def delete_slack_message(self, msg_id: str) -> None:
        """Delete a Slack message (compensating action)."""
        if msg_id in self.sent_messages:
            self.sent_messages.remove(msg_id)
            print(f"  [Slack] ROLLBACK: deleted message {msg_id}")

    def insert_record(self, table: str, data: dict) -> str:
        """Insert a database record - returns record ID."""
        record_id = f"REC-{len(self.database_records) + 1}"
        self.database_records.append({"id": record_id, "table": table, **data})
        print(f"  [DB] inserted record {record_id} into {table}")
        return record_id

    def delete_record(self, record_id: str) -> None:
        """Delete a database record (compensating action)."""
        self.database_records = [
            r for r in self.database_records if r["id"] != record_id
        ]
        print(f"  [DB] ROLLBACK: deleted record {record_id}")


# Global instance for this demo (in production, use dependency injection or Prefect artifacts)
systems = ExternalSystems()


# ## Transactional Tasks with Rollback Hooks
#
# Each task registers its result in the transaction context.
# The `on_rollback` hook knows how to undo the side effect.


def register_for_rollback(resource_type: str, resource_id: str):
    """Register a created resource for potential rollback."""
    txn = get_transaction()
    if txn:
        # Defensive copy - don't mutate the list in place
        created = list(txn.get("created_resources", []))
        created.append((resource_type, resource_id))
        txn.set("created_resources", created)


@task
def create_issue_task(title: str, body: str) -> str:
    """Task that creates a GitHub issue with rollback capability."""
    issue_id = systems.create_github_issue(title, body)
    register_for_rollback("github_issue", issue_id)
    return issue_id


@create_issue_task.on_rollback
def rollback_issues(txn):
    """Compensating action: delete created issues."""
    for rtype, rid in txn.get("created_resources", []):
        if rtype == "github_issue":
            systems.delete_github_issue(rid)


@task
def notify_team_task(channel: str, message: str) -> str:
    """Task that sends a Slack message with rollback capability."""
    msg_id = systems.send_slack_message(channel, message)
    register_for_rollback("slack_message", msg_id)
    return msg_id


@notify_team_task.on_rollback
def rollback_notifications(txn):
    """Compensating action: delete sent messages."""
    for rtype, rid in txn.get("created_resources", []):
        if rtype == "slack_message":
            systems.delete_slack_message(rid)


@task
def log_action_task(action: str, details: str) -> str:
    """Task that logs to database with rollback capability."""
    record_id = systems.insert_record(
        "audit_log", {"action": action, "details": details}
    )
    register_for_rollback("db_record", record_id)
    return record_id


@log_action_task.on_rollback
def rollback_logs(txn):
    """Compensating action: delete audit records."""
    for rtype, rid in txn.get("created_resources", []):
        if rtype == "db_record":
            systems.delete_record(rid)


# ## Agent Tools
#
# These are thin wrappers that the pydantic-ai agent calls.
# Each tool delegates to a Prefect task with rollback capability.


def create_issue(ctx: RunContext[None], title: str, body: str) -> str:
    """Create a GitHub issue to track an incident.

    Args:
        title: The issue title
        body: The issue description
    """
    return create_issue_task(title, body)


def notify_team(ctx: RunContext[None], channel: str, message: str) -> str:
    """Send a Slack notification to alert the team.

    Args:
        channel: The Slack channel (e.g., 'engineering')
        message: The notification message
    """
    return notify_team_task(channel, message)


def log_action(ctx: RunContext[None], action: str, details: str) -> str:
    """Log an action to the audit database.

    Args:
        action: The action type (e.g., 'incident_created')
        details: Details about the action
    """
    return log_action_task(action, details)


# ## The AI Agent
#
# A pydantic-ai agent that responds to incidents by:
# 1. Creating a GitHub issue
# 2. Notifying the team on Slack
# 3. Logging the action for audit


class IncidentResponse(BaseModel):
    """Structured output from the incident response agent."""

    summary: str = Field(description="Summary of actions taken")
    issue_id: str | None = Field(default=None, description="GitHub issue ID if created")
    notification_sent: bool = Field(
        default=False, description="Whether team was notified"
    )


incident_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=IncidentResponse,
    system_prompt="""You are an incident response agent. When given an incident report:
1. First, create a GitHub issue to track the incident
2. Then, notify the engineering team on the 'engineering' Slack channel
3. Finally, log your actions for audit

Always complete all three steps in order. Use the tools provided.""",
    tools=[create_issue, notify_team, log_action],
)


# ## Transactional Agent Execution
#
# The key insight: wrap the entire agent run in a `transaction()` context.
# If any tool fails, all previous side effects are automatically rolled back.


@flow(name="transactional-incident-response", log_prints=True)
async def handle_incident(
    incident_report: str,
    simulate_failure: bool = False,
) -> IncidentResponse | None:
    """
    Handle an incident using an AI agent with transactional semantics.

    If any tool call fails, all previous side effects are rolled back.
    This is the SAGA pattern applied to AI agents.

    Args:
        incident_report: Description of the incident
        simulate_failure: If True, simulate a Slack API failure
    """
    print(f"\n{'=' * 60}")
    print("TRANSACTIONAL INCIDENT RESPONSE")
    print(f"{'=' * 60}")

    # Reset state for clean demo
    systems.created_issues.clear()
    systems.sent_messages.clear()
    systems.database_records.clear()
    systems.fail_on_notification = simulate_failure

    print(f"\nincident: {incident_report}")
    print(f"simulate failure: {simulate_failure}")

    try:
        # THE KEY: Wrap agent execution in a transaction
        with transaction():
            print("\nagent starting (all tool calls are transactional)...\n")

            result = await incident_agent.run(
                f"Handle this incident: {incident_report}",
            )

            print(f"\nagent completed: {result.output.summary}")
            return result.output

    except Exception as e:
        print(f"\nagent failed: {e}")
        print("all side effects have been rolled back")
        return None

    finally:
        print(f"\n{'=' * 60}")
        print("FINAL STATE")
        print(f"{'=' * 60}")
        print(f"github issues: {systems.created_issues}")
        print(f"slack messages: {systems.sent_messages}")
        print(f"database records: {[r['id'] for r in systems.database_records]}")


# ## Running the Example
#
# Run with successful execution:
# ```bash
# uv run python examples/transactional_ai_agent.py
# ```
#
# The agent will:
# 1. Create a GitHub issue ✓
# 2. Send a Slack notification ✓
# 3. Log to database ✓
# → All side effects persist
#
# Run with simulated failure:
# ```bash
# uv run python examples/transactional_ai_agent.py --fail
# ```
#
# The agent will:
# 1. Create a GitHub issue ✓
# 2. Send a Slack notification ✗ (fails)
# → GitHub issue is automatically rolled back
# → No orphaned side effects


if __name__ == "__main__":
    import asyncio
    import os
    import sys

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set")
        print("export OPENAI_API_KEY='your-key'")
        sys.exit(1)

    simulate_failure = "--fail" in sys.argv

    print("\n" + "=" * 60)
    if simulate_failure:
        print("RUNNING WITH SIMULATED SLACK FAILURE")
        print("Watch: GitHub issue created, then rolled back on Slack failure")
    else:
        print("RUNNING NORMALLY")
        print("Watch: All three tools succeed, side effects persist")
    print("=" * 60)

    asyncio.run(
        handle_incident(
            "Production API returning 500 errors on /users endpoint",
            simulate_failure=simulate_failure,
        )
    )

# ## Key Takeaways
#
# **The Problem**: MCP enables tool calling but doesn't handle rollback.
# When an agent creates resources across multiple systems, a failure mid-way
# leaves orphaned side effects.
#
# **The Solution**: Prefect transactions with `on_rollback` hooks implement
# the SAGA pattern for AI agents:
#
# 1. **Wrap agent execution** in `with transaction():`
# 2. **Register compensating actions** via `@task.on_rollback`
# 3. **Store context** with `txn.set()` / `txn.get()` for rollback hooks
#
# **This pattern works with any MCP server** - filesystem, GitHub, Slack,
# databases, or custom tools. Each tool just needs a compensating action.
#
# ## Related Documentation
#
# - [Transactional workflows](/v3/advanced/transactions) - Full guide to Prefect transactions
# - [Task lifecycle hooks](/v3/how-to-guides/workflows/state-change-hooks) - on_commit and on_rollback hooks
# - [pydantic-ai + Prefect](https://ai.pydantic.dev/durable_execution/prefect/) - Durable AI agents
# - [SAGA pattern](https://microservices.io/patterns/data/saga.html) - The distributed transaction pattern
