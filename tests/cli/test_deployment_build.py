import pytest

from prefect import flow
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def dep_path():
    return "./dog.py"


@pytest.fixture
def patch_import(monkeypatch):
    @flow
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

    def test_providing_tags_is_deprecated(self, dep_path, patch_import):
        invoke_and_assert(
            ["deployment", "build", dep_path + ":flow", "-n", "dog", "-t", "blue"],
            expected_output_contains=["Providing tags for deployments is deprecated"],
        )
