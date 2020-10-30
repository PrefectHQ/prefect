import pytest

from prefect.tasks.jupyter import JupyterTask

pytest.importorskip("papermill")


def test_jupyter():
    task = JupyterTask(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        notebook_params=dict(a=5),
        as_html=True,
    )
    output = task.run()
    assert "a*b=10" in output
