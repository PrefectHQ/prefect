"""
CloudWatch logging functionality for ECS worker.
"""

import logging
import sys
from copy import deepcopy
from typing import Any, List, Optional


def mask_sensitive_env_values(
    task_run_request: dict, values: List[str], keep_length=3, replace_with="***"
):
    for container in task_run_request.get("overrides", {}).get(
        "containerOverrides", []
    ):
        for env_var in container.get("environment", []):
            if (
                "name" not in env_var
                or "value" not in env_var
                or env_var["name"] not in values
            ):
                continue
            if len(env_var["value"]) > keep_length:
                # Replace characters beyond the keep length
                env_var["value"] = env_var["value"][:keep_length] + replace_with
    return task_run_request


def mask_api_key(task_run_request):
    return mask_sensitive_env_values(
        deepcopy(task_run_request), ["PREFECT_API_KEY"], keep_length=6
    )


def stream_available_logs(
    logger: logging.Logger,
    logs_client: Any,
    log_group: str,
    log_stream: str,
    last_log_timestamp: Optional[int] = None,
) -> Optional[int]:
    """
    Stream logs from the given log group and stream since the last log timestamp.

    Will continue on paginated responses until all logs are returned.

    Returns the last log timestamp which can be used to call this method in the
    future.
    """
    last_log_stream_token = "NO-TOKEN"
    next_log_stream_token = None

    # AWS will return the same token that we send once the end of the paginated
    # response is reached
    while last_log_stream_token != next_log_stream_token:
        last_log_stream_token = next_log_stream_token

        request = {
            "logGroupName": log_group,
            "logStreamName": log_stream,
        }

        if last_log_stream_token is not None:
            request["nextToken"] = last_log_stream_token

        if last_log_timestamp is not None:
            # Bump the timestamp by one ms to avoid retrieving the last log again
            request["startTime"] = last_log_timestamp + 1

        try:
            response = logs_client.get_log_events(**request)
        except Exception:
            logger.error(
                f"Failed to read log events with request {request}",
                exc_info=True,
            )
            return last_log_timestamp

        log_events = response["events"]
        for log_event in log_events:
            # TODO: This doesn't forward to the local logger, which can be
            #       bad for customizing handling and understanding where the
            #       log is coming from, but it avoid nesting logger information
            #       when the content is output from a Prefect logger on the
            #       running infrastructure
            print(log_event["message"], file=sys.stderr)

            if (
                last_log_timestamp is None
                or log_event["timestamp"] > last_log_timestamp
            ):
                last_log_timestamp = log_event["timestamp"]

        next_log_stream_token = response.get("nextForwardToken")
        if not log_events:
            # Stop reading pages if there was no data
            break

    return last_log_timestamp
