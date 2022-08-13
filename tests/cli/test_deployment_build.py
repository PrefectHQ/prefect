import os

import pytest

from prefect import flow
from prefect.deployments import Deployment
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def dep_path():
    return "./dog.py"


@pytest.fixture
def patch_import(monkeypatch):
    @flow(description="Need a non-trivial description here.", version="A")
    def fn():
        pass

    monkeypatch.setattr("prefect.utilities.importtools.import_object", lambda path: fn)


class TestInputValidation:
    def test_useful_message_when_flow_name_skipped(self, dep_path):
        invoke_and_assert(
            ["deployment", "build", dep_path, "-n", "dog-deployment"],
            expected_output_contains=[
                "Your flow path must include the name of the function that is the entrypoint to your flow.",
                f"Try {dep_path}:<flow_name> for your flow path.",
            ],
            expected_code=1,
        )

    def test_name_must_be_provided_by_default(self, dep_path):
        invoke_and_assert(
            ["deployment", "build", dep_path],
            expected_output_contains=["A name for this deployment must be provided"],
            expected_code=1,
        )

    def test_server_side_settings_are_used_if_present(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
            description="server-side value",
            version="server",
        )
        assert d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "--ignore-file",
                "foobar",
            ],
            expected_code=0,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.description == "server-side value"
        assert deployment.version == "server"

    def test_version_flag_takes_precedence(self, patch_import, tmp_path):
        d = Deployment(
            name="TEST",
            flow_name="fn",
            version="server",
        )
        assert d.apply()

        invoke_and_assert(
            [
                "deployment",
                "build",
                "fake-path.py:fn",
                "-n",
                "TEST",
                "-o",
                str(tmp_path / "test.yaml"),
                "-v",
                "CLI-version",
                "--ignore-file",
                "foobar",
            ],
            expected_code=0,
        )

        deployment = Deployment.load_from_yaml(tmp_path / "test.yaml")
        assert deployment.version == "CLI-version"


def test_yaml_comment_for_work_queue(dep_path, patch_import):
    invoke_and_assert(
        ["deployment", "build", dep_path + ":flow", "-n", "dog"],
    )
    yaml_path = "./flow-deployment.yaml"
    try:
        with open(yaml_path, "r") as f:
            contents = f.readlines()

        comment_index = contents.index(
            "# The work queue that will handle this deployment's runs\n"
        )
        assert contents[comment_index + 1] == "work_queue_name: null\n"

    finally:
        os.remove(yaml_path)
