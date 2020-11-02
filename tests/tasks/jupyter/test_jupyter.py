import json

import pytest

from prefect.tasks.jupyter import JupyterTask

pytest.importorskip("papermill")


def test_jupyter_html_output():
    task = JupyterTask(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        notebook_params=dict(a=5),
        as_html=True,
    )
    output = task.run()
    assert "a*b=10" in output


def test_jupyter_json_output():
    task = JupyterTask(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        notebook_params=dict(a=5),
        as_html=False,
    )
    output = task.run()
    nbobject = json.loads(output)  # try loading the JSON string
    assert "a*b=10" in output
