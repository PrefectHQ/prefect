import glob
import shutil
from pathlib import Path

import pytest

from prefect.testing.cli import invoke_and_assert


class TestInputValidation:
    def test_useful_message_when_flow_name_skipped(self):
        invoke_and_assert(
            ["deployment", "build", "./dog.py", "-n", "dog-deployment"],
            expected_output_contains=[
                "Your flow path must include the name of the function that is the entrypoint to your flow.",
                "Try ./dog.py:<flow_name> for your flow path.",
            ],
            expected_code=1,
        )

    def test_name_must_be_provided_by_default(self):
        invoke_and_assert(
            ["deployment", "build", "./dog.py"],
            expected_output_contains=["A name for this deployment must be provided"],
            expected_code=1,
        )


class TestManifestGeneration:
    @pytest.fixture
    def cwd(self, tmp_path):
        """Uses a local file system method to copy `examples/` to a temporary directory
        from which CLI commands can be run."""
        fpath = Path(__file__).parent / "example-project"
        shutil.copytree(fpath, tmp_path / "example-project")
        return tmp_path / "example-project"

    def test_manifest_only_creation(self, cwd):
        invoke_and_assert(
            [
                "deployment",
                "build",
                f"{cwd}/flows/hello.py:my_flow",
                "-n",
                "test-me",
                "--manifest-only",
            ],
            expected_output_contains=["Manifest created"],
            expected_code=0,
            temp_dir=str(cwd),
        )
        res = glob.glob(f"{cwd}/**/**", recursive=True)
        assert len({p for p in res if p.endswith("-manifest.json")}) == 1
        assert len({p for p in res if p.endswith("-deployment.yaml")}) == 0

    def test_manifest_only_creation_does_not_require_name(self, cwd):
        invoke_and_assert(
            [
                "deployment",
                "build",
                f"{cwd}/flows/hello.py:my_flow",
                "--manifest-only",
            ],
            expected_output_contains=["Manifest created"],
            expected_code=0,
            temp_dir=str(cwd),
        )
        res = glob.glob(f"{cwd}/**/**", recursive=True)
        assert len({p for p in res if p.endswith("-manifest.json")}) == 1
        assert len({p for p in res if p.endswith("-deployment.yaml")}) == 0
