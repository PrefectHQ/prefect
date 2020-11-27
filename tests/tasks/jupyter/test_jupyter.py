import json
from nbconvert import HTMLExporter

from prefect.tasks.jupyter import ExecuteNotebook


def test_jupyter_html_output():
    task = ExecuteNotebook(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        parameters=dict(a=5),
        output_format="html",
    )
    output = task.run()
    assert "a*b=10" in output


def test_jupyter_custom_exporter():
    exporter = HTMLExporter()

    task = ExecuteNotebook(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        parameters=dict(a=5),
        exporter=exporter,
    )
    output = task.run()
    assert "a*b=10" in output


def test_jupyter_json_output():
    task = ExecuteNotebook(
        "tests/tasks/jupyter/sample_notebook.ipynb",
        parameters=dict(a=5),
        output_format="json",
    )
    output = task.run()
    _ = json.loads(output)  # try loading the JSON string
    assert "a*b=10" in output
