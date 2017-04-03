from contextlib import contextmanager as _contextmanager
context = {}


@_contextmanager
def prefect_context(
        dt, flow_id, flow_namespace, flow_name, flow_version, task_id,
        task_name, run_number, pipes, params):
    context.update(
        dict(
            dt=dt,
            flow_id=flow_id,
            flow_namespace=flow_namespace,
            flow_name=flow_name,
            flow_version=flow_version,
            task_id=task_id,
            task_name=task_name,
            run_number=run_number,
            pipes=pipes,
            params=params,))
    try:
        yield context
    finally:
        context.clear()
