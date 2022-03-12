"""
This is a collection of tasks to interact with a Cube.js or Cube Cloud environment.
"""

try:
    from prefect.tasks.cubejs.cubejs_tasks import CubeJSQueryTask
except ImportError as err:
    raise ImportError(
        'prefect.tasks.cubejs` requires Prefect to be installed with the "cubejs" extra.'
    ) from err
