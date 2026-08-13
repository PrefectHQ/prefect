"""
Utilities for following flow runs with interleaved events and logs
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import anyio
from rich.console import Console

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import Log, StateType
from prefect.events import Event
from prefect.events.subscribers import FlowRunSubscriber
from prefect.exceptions import FlowRunWaitTimeout, FlowRunWatchError

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun


# Color mapping for state types
STATE_TYPE_COLORS: dict[StateType, str] = {
    StateType.SCHEDULED: "yellow",
    StateType.PENDING: "bright_black",
    StateType.RUNNING: "blue",
    StateType.COMPLETED: "green",
    StateType.FAILED: "red",
    StateType.CANCELLED: "bright_black",
    StateType.CANCELLING: "bright_black",
    StateType.CRASHED: "orange1",
    StateType.PAUSED: "bright_black",
}


async def watch_flow_run(
    flow_run_id: UUID, console: Console, timeout: int | None = None
) -> FlowRun:
    """
    Watch a flow run, displaying interleaved events and logs until completion.

    Args:
        flow_run_id: The ID of the flow run to watch
        console: Rich console for output
        timeout: Maximum time to wait for flow run completion in seconds.
                 If None, waits indefinitely.

    Returns:
        The finished flow run

    Raises:
        FlowRunWaitTimeout: If the flow run exceeds the timeout
        FlowRunWatchError: If the events/logs stream closes before the flow run
            reaches a terminal state
    """
    formatter = FlowRunFormatter()
    subscriber = FlowRunSubscriber(flow_run_id=flow_run_id)

    async def consume() -> Exception | None:
        entered_subscriber = False
        try:
            async with subscriber:
                entered_subscriber = True
                while True:
                    try:
                        item = await anext(subscriber)
                    except StopAsyncIteration:
                        return None
                    except Exception as exc:
                        return exc

                    console.print(formatter.format(item))
        except Exception as exc:
            if entered_subscriber:
                raise
            return exc

    if timeout is not None:
        with anyio.move_on_after(timeout) as cancel_scope:
            stream_error = await consume()

        if cancel_scope.cancelled_caught:
            raise FlowRunWaitTimeout(
                f"Flow run with ID {flow_run_id} exceeded watch timeout of {timeout} seconds"
            )
    else:
        stream_error = await consume()

    try:
        async with get_client() as client:
            flow_run = await client.read_flow_run(flow_run_id)
    except Exception:
        if stream_error is not None:
            raise FlowRunWatchError(
                f"Stopped watching flow run {flow_run_id} before it reached a "
                "terminal state; the events or logs stream closed unexpectedly "
                "and the final state could not be read."
            ) from stream_error
        raise

    # A stream may terminate just as the run finishes, so reconcile against the
    # server before deciding whether the watch failed.
    state = flow_run.state
    if state is None or not state.is_final():
        raise FlowRunWatchError(
            f"Stopped watching flow run {flow_run_id} before it reached a terminal "
            "state because the events or logs stream closed unexpectedly."
        ) from stream_error

    return flow_run


class FlowRunFormatter:
    """Handles formatting of logs and events for CLI display"""

    def __init__(self):
        self._last_timestamp_parts = ["", "", "", ""]
        self._last_datetime: datetime | None = None

    def format_timestamp(self, dt: datetime) -> str:
        """Format timestamp with incremental display"""
        ms = dt.strftime("%f")[:3]
        current_parts = [dt.strftime("%H"), dt.strftime("%M"), dt.strftime("%S"), ms]

        if self._last_datetime and dt < self._last_datetime:
            self._last_timestamp_parts = current_parts[:]
            self._last_datetime = dt
            return f"{current_parts[0]}:{current_parts[1]}:{current_parts[2]}.{current_parts[3]}"

        display_parts = []
        for i, (last, current) in enumerate(
            zip(self._last_timestamp_parts, current_parts)
        ):
            if current != last:
                display_parts = current_parts[i:]
                break
        else:
            display_parts = [current_parts[3]]

        self._last_timestamp_parts = current_parts[:]
        self._last_datetime = dt

        if len(display_parts) == 4:
            timestamp_str = f"{display_parts[0]}:{display_parts[1]}:{display_parts[2]}.{display_parts[3]}"
        elif len(display_parts) == 3:
            timestamp_str = f":{display_parts[0]}:{display_parts[1]}.{display_parts[2]}"
        elif len(display_parts) == 2:
            timestamp_str = f":{display_parts[0]}.{display_parts[1]}"
        else:
            timestamp_str = f".{display_parts[0]}"

        return f"{timestamp_str:>12}"

    def format_run_id(self, run_id_short: str) -> str:
        """Format run ID"""
        return f"{run_id_short:>12}"

    def format(self, item: Log | Event) -> str:
        """Format a log or event for display"""
        if isinstance(item, Log):
            return self.format_log(item)
        else:
            return self.format_event(item)

    def format_log(self, log: Log) -> str:
        """Format a log entry"""
        timestamp = self.format_timestamp(log.timestamp)

        run_id = log.task_run_id or log.flow_run_id
        run_id_short = str(run_id)[-12:] if run_id else "............"
        run_id_display = self.format_run_id(run_id_short)

        icon = "▪"
        prefix_plain = f"{icon} {timestamp.strip()} {run_id_display.strip()} "

        lines = log.message.split("\n")
        if len(lines) == 1:
            return f"[dim]▪[/dim] {timestamp} [dim]{run_id_display}[/dim] {log.message}"

        first_line = f"[dim]▪[/dim] {timestamp} [dim]{run_id_display}[/dim] {lines[0]}"
        indent = " " * len(prefix_plain)
        continuation_lines = [f"{indent}{line}" for line in lines[1:]]

        return first_line + "\n" + "\n".join(continuation_lines)

    def format_event(self, event: Event) -> str:
        """Format an event"""
        timestamp = self.format_timestamp(event.occurred)

        run_id = None

        if event.resource.id.startswith("prefect.task-run."):
            run_id = event.resource.id.split(".", 2)[2]
        elif event.resource.id.startswith("prefect.flow-run."):
            run_id = event.resource.id.split(".", 2)[2]

        if not run_id:
            for related in event.related:
                if related.id.startswith("prefect.task-run."):
                    run_id = related.id.split(".", 2)[2]
                    break
                elif related.id.startswith("prefect.flow-run."):
                    run_id = related.id.split(".", 2)[2]
                    break

        run_id_short = run_id[-12:] if run_id else "............"
        run_id_display = self.format_run_id(run_id_short)

        # Get state type from event resource or payload
        state_type_str = event.resource.get("prefect.state-type")
        if not state_type_str and "validated_state" in event.payload:
            state_type_str = event.payload["validated_state"].get("type")

        # Map state type to color
        color = "bright_magenta"  # default for unknown states
        if state_type_str:
            try:
                state_type = StateType(state_type_str)
                color = STATE_TYPE_COLORS.get(state_type, "bright_magenta")
            except ValueError:
                pass

        name = event.resource.get("prefect.resource.name") or event.resource.id
        return (
            f"[{color}]●[/{color}] {timestamp} [dim]{run_id_display}[/dim] "
            f"{event.event} * [bold cyan]{name}[/bold cyan]"
        )
