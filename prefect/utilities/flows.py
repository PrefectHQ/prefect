import prefect

DEFAULT_FLOW = None


def reset_default_flow():
    global DEFAULT_FLOW
    flow_name = prefect.config.get("flows", "global_default_flow")
    if flow_name and flow_name != "None":
        DEFAULT_FLOW = prefect.Flow("Default Flow")
        prefect.context.Context.update(flow=DEFAULT_FLOW)


def get_default_flow():
    return DEFAULT_FLOW


def get_flow_by_id(id):
    """
    Retrieves a flow by its ID. This will only work for Flows that are alive
    in the current interpreter.
    """
    return prefect.core.flow.FLOW_REGISTRY.get(id)
