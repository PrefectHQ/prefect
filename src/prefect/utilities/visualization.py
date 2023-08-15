from uuid import UUID

import graphviz

from prefect.client.utilities import inject_client
from prefect.client.orchestration import PrefectClient


@inject_client
async def task_run_dependencies_graph(
    flow_run_id: UUID,
    client: "PrefectClient" = None,
) -> graphviz.Digraph:
    """
    Return a graphviz graph of the task run dependencies for a flow run.
    """
    task_runs = await client.graph(flow_run_id)

    id_to_name = {task_run.id: task_run.name for task_run in task_runs}
    edges = []
    for task_run in task_runs:
        for dependency in task_run.upstream_dependencies:
            if dependency.input_type == "task_run":
                name = id_to_name[dependency.id]
                edges.append((name, task_run.name))

    g = graphviz.Digraph()
    for edge in edges:
        g.edge(*edge)

    return g
