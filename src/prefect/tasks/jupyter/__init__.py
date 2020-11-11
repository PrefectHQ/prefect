"""
A collection of tasks for running Jupyter notebooks.
"""
try:
    from prefect.tasks.jupyter.jupyter import ExecuteNotebook
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.jupyter` requires Prefect to be installed with the "jupyter" extra.'
    )
