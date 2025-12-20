# ---
# title: Transactional AI Agent with Rollback
# description: Build AI agents with automatic rollback when tools fail - the SAGA pattern for agentic workflows.
# icon: rotate-left
# dependencies: ["prefect", "pydantic-ai[prefect]"]
# keywords: ["ai", "agents", "pydantic-ai", "transactions", "rollback", "saga", "side-effects"]
# order: 8
# ---
#
# AI agents are while loops that call tools. Those tools have side effects -
# creating issues, sending messages, updating databases. But what happens when
# tool #3 fails after tools #1 and #2 already ran?
#
# Without transactional semantics, you're left with orphaned side effects:
# - A GitHub issue that shouldn't exist
# - A Slack notification about something that didn't complete
# - Partial database updates
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
# * **PrefectAgent integration** - Tools wrapped as Prefect tasks participate in transactions
#
# ## Setup
#
# ```bash
# uv add prefect pydantic-ai[prefect]
# export OPENAI_API_KEY='your-key'
# ```

from dataclasses import dataclass, field
from functools import partial

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.durable_exec.prefect import PrefectAgent

from prefect import flow
from prefect.transactions import transaction

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
    fail_on_pagerduty: bool = False

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

    def send_pagerduty_alert(self, severity: str, description: str) -> str:
        """Send a PagerDuty alert - fails when fail_on_pagerduty is True."""
        if self.fail_on_pagerduty:
            raise RuntimeError("PagerDuty API error: service unavailable")
        alert_id = f"PD-{len(self.database_records) + 1}"
        print(f"  [PagerDuty] sent alert {alert_id}: {description}")
        return alert_id

    def rollback_all(self) -> None:
        """Undo all side effects - the compensating transaction."""
        # Process in reverse order (LIFO) - undo most recent first
        for record in reversed(list(self.database_records)):
            self.delete_record(record["id"])
        for msg_id in reversed(list(self.sent_messages)):
            self.delete_slack_message(msg_id)
        for issue_id in reversed(list(self.created_issues)):
            self.delete_github_issue(issue_id)


# ## Agent Tools
#
# These are the tools the AI agent can call. Each tool performs a side effect.
# The ExternalSystems object tracks all created resources, so on rollback
# we can undo everything.


def create_issue(ctx: RunContext[ExternalSystems], title: str, body: str) -> str:
    """Create a GitHub issue to track an incident.

    Args:
        title: The issue title
        body: The issue description
    """
    return ctx.deps.create_github_issue(title, body)


def notify_team(ctx: RunContext[ExternalSystems], channel: str, message: str) -> str:
    """Send a Slack notification to alert the team.

    Args:
        channel: The Slack channel (e.g., 'engineering')
        message: The notification message
    """
    return ctx.deps.send_slack_message(channel, message)


def log_action(ctx: RunContext[ExternalSystems], action: str, details: str) -> str:
    """Log an action to the audit database.

    Args:
        action: The action type (e.g., 'incident_created')
        details: Details about the action
    """
    return ctx.deps.insert_record("audit_log", {"action": action, "details": details})


def send_alert(
    ctx: RunContext[ExternalSystems], severity: str, description: str
) -> str:
    """Send a PagerDuty alert for critical incidents.

    Args:
        severity: Alert severity (critical, warning, info)
        description: Alert description
    """
    return ctx.deps.send_pagerduty_alert(severity, description)


# ## Rollback Handler
#
# Execute compensating actions for all created resources when the transaction fails.


def execute_rollbacks(systems: ExternalSystems, txn) -> None:
    """Execute compensating actions for all created resources."""
    systems.rollback_all()


# ## The AI Agent
#
# A pydantic-ai agent that responds to incidents by:
# 1. Creating a GitHub issue
# 2. Notifying the team on Slack
# 3. Logging the action for audit
# 4. Sending a PagerDuty alert (this one fails to demonstrate rollback)


class IncidentResponse(BaseModel):
    """Structured output from the incident response agent."""

    summary: str = Field(description="Summary of actions taken")
    issue_id: str | None = Field(default=None, description="GitHub issue ID if created")
    notification_sent: bool = Field(
        default=False, description="Whether team was notified"
    )


base_agent = Agent(
    "openai:gpt-4o-mini",
    name="incident-response-agent",
    output_type=IncidentResponse,
    deps_type=ExternalSystems,
    tools=[create_issue, notify_team, log_action, send_alert],
    system_prompt="""You are an incident response agent. When given an incident report:
1. First, create a GitHub issue to track the incident
2. Then, notify the engineering team on the 'engineering' Slack channel
3. Log your actions for audit
4. Finally, send a PagerDuty alert

Always complete all four steps in order. Use the tools provided.""",
)

# Wrap with PrefectAgent for durable execution
# This makes tool calls become Prefect tasks that participate in transactions
incident_agent = PrefectAgent(base_agent)


# ## Transactional Agent Execution
#
# The key insight: wrap the entire agent run in a `transaction()` context.
# If anything fails, Prefect's transaction system triggers the rollback hook.


class IncidentReport(BaseModel):
    """Input for the incident response flow."""

    title: str = Field(description="Short incident title")
    description: str = Field(description="Detailed incident description")
    severity: str = Field(
        default="warning", description="Severity: critical, warning, info"
    )


@flow(name="transactional-incident-response", log_prints=True)
async def handle_incident(
    incident: IncidentReport,
    simulate_failure: bool = False,
) -> IncidentResponse | None:
    """
    Handle an incident using an AI agent with transactional semantics.

    If any tool call fails, all previous side effects are rolled back.
    This is the SAGA pattern applied to AI agents.

    Args:
        incident: The incident report to handle
        simulate_failure: If True, simulate a PagerDuty API failure
    """
    print(f"\n{'=' * 60}")
    print("TRANSACTIONAL INCIDENT RESPONSE")
    print(f"{'=' * 60}")

    # Create external systems with failure simulation
    systems = ExternalSystems(fail_on_pagerduty=simulate_failure)

    print(f"\nincident: {incident.title}")
    print(f"severity: {incident.severity}")
    print(f"simulate failure: {simulate_failure}")

    try:
        with transaction() as txn:
            # Register rollback handler - will undo all side effects on failure
            txn.on_rollback_hooks.append(partial(execute_rollbacks, systems))

            print("\nagent starting (all tool calls are transactional)...\n")

            prompt = f"""Handle this {incident.severity} incident:
Title: {incident.title}
Description: {incident.description}

This is a {incident.severity} incident so you must send a PagerDuty alert."""

            result = await incident_agent.run(prompt, deps=systems)

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
# 4. Send PagerDuty alert ✓
# → All side effects persist
#
# Run with simulated failure:
# ```bash
# uv run python examples/transactional_ai_agent.py --fail
# ```
#
# The agent will:
# 1. Create a GitHub issue ✓
# 2. Send a Slack notification ✓
# 3. Log to database ✓
# 4. Send PagerDuty alert ✗ (fails)
# → All previous side effects are rolled back
# → No orphaned resources


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
        print("RUNNING WITH SIMULATED PAGERDUTY FAILURE")
        print("Watch: Resources created, then rolled back on PagerDuty failure")
    else:
        print("RUNNING NORMALLY")
        print("Watch: All four tools succeed, side effects persist")
    print("=" * 60)

    asyncio.run(
        handle_incident(
            IncidentReport(
                title="Production API returning 500 errors",
                description="The /users endpoint is returning 500 errors for 10% of requests",
                severity="critical",
            ),
            simulate_failure=simulate_failure,
        )
    )

# ## Key Takeaways
#
# **The Problem**: AI agents call tools that have side effects. When a tool fails
# mid-workflow, you're left with orphaned resources - issues that shouldn't exist,
# notifications about incomplete actions, partial database updates.
#
# **The Solution**: Prefect transactions with `on_rollback_hooks` implement
# the SAGA pattern for AI agents:
#
# 1. **Wrap agent execution** in `with transaction():`
# 2. **Register compensating actions** via `txn.on_rollback_hooks.append()`
# 3. **Track resources** on your domain objects for the rollback handler
# 4. **Use PrefectAgent** to make tool calls participate in transactions
#
# This pattern works with any tool - filesystem, GitHub, Slack,
# databases, or custom APIs. Each tool just needs a compensating action.
#
# ## Related Documentation
#
# - [Transactional workflows](/v3/advanced/transactions) - Full guide to Prefect transactions
# - [Task lifecycle hooks](/v3/how-to-guides/workflows/state-change-hooks) - on_commit and on_rollback hooks
# - [pydantic-ai + Prefect](https://ai.pydantic.dev/durable_execution/prefect/) - Durable AI agents
# - [SAGA pattern](https://microservices.io/patterns/data/saga.html) - The distributed transaction pattern
