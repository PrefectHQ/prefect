from click.testing import CliRunner
from prefect.cli.delete import delete


def test_delete_init():
    runner = CliRunner()
    result = runner.invoke(delete)
    assert result.exit_code == 0
    assert (
        "Delete commands that refer to mutations of Prefect API metadata."
        in result.output
    )


def test_delete_help():
    runner = CliRunner()
    result = runner.invoke(delete, ["--help"])
    assert result.exit_code == 0
    assert (
        "Delete commands that refer to mutations of Prefect API metadata."
        in result.output
    )


def test_delete_project(patch_post):
    patch_post(
        {"data": {"project": [{"id": "test"}], "delete_project": {"success": True}}}
    )

    runner = CliRunner()
    result = runner.invoke(delete, ["project", "test"])
    assert result.exit_code == 0
    assert "test deleted" in result.output


def test_delete_project_error(patch_post):
    patch_post(dict(data=dict(project={})))

    runner = CliRunner()
    result = runner.invoke(delete, ["project", "test"])
    assert result.exit_code == 0
    assert "Error deleting project" in result.output
