from prefect.context import FlowRunContext, TaskRunContext


def get_related_resource_from_context() -> list[dict[str, str]]:
    """Get the related resource from the context."""
    related: list[dict[str, str]] = []
    if context := TaskRunContext.get():
        related.append(
            {
                "prefect.resource.id": f"prefect.task-run.{context.task_run.id}",
                "prefect.resource.name": context.task_run.name,
                "prefect.resource.role": "task-run",
            }
        )
    if flow_run_context := FlowRunContext.get():
        if flow_run_context.flow_run:
            related.append(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run_context.flow_run.id}",
                    "prefect.resource.name": flow_run_context.flow_run.name,
                    "prefect.resource.role": "flow-run",
                }
            )
            if flow_run_context.flow:
                related.append(
                    {
                        "prefect.resource.id": f"prefect.flow.{flow_run_context.flow_run.flow_id}",
                        "prefect.resource.name": flow_run_context.flow.name,
                        "prefect.resource.role": "flow",
                    }
                )
    return related
