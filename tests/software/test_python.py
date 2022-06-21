from textwrap import dedent

from prefect.software.pip import PipRequirement
from prefect.software.python import PythonRequirements


class TestPythonRequirements:
    def test_init(self):
        reqs = PythonRequirements(pip_requirements=["foo", "bar>=2"])
        assert reqs.pip_requirements == [
            PipRequirement("foo"),
            PipRequirement("bar>=2"),
        ]

    def test_from_requirements_file(self, tmp_path):
        reqs_file = tmp_path / "requirements.txt"
        reqs_file.write_text(
            dedent(
                """
                foo
                bar>=2
                """
            )
        )

        reqs = PythonRequirements.from_requirements_file(reqs_file)
        assert reqs.pip_requirements == [
            PipRequirement("foo"),
            PipRequirement("bar>=2"),
        ]

    def test_to_requirements_file(self, tmp_path):
        reqs_file = tmp_path / "requirements.txt"
        reqs = PythonRequirements(pip_requirements=["foo", "bar>=2"])

        reqs.to_requirements_file(reqs_file)
        assert (
            reqs_file.read_text()
            == dedent(
                """
                foo
                bar>=2
                """
            ).strip()
        )
