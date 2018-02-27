import prefect

DEFAULT_FLOW = None

def reset_default_flow():
    global DEFAULT_FLOW
    flow_name = prefect.config.get('flows', 'global_default_flow')
    if flow_name:
        DEFAULT_FLOW = prefect.Flow('Default Flow')
        prefect.context.Context.update(flow=DEFAULT_FLOW)


def get_default_flow():
    return DEFAULT_FLOW
