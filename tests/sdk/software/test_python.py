from textwrap import dedent

from prefect.software.pip import PipRequirement
from prefect.software.python import PythonEnvironment


class TestPythonEnvironment:
    def test_init(self):
        reqs = PythonEnvironment(pip_requirements=["foo", "bar>=2"])
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
        reqs = PythonEnvironment.from_file(reqs_file)
        assert reqs.pip_requirements == [
            PipRequirement("foo"),
            PipRequirement("bar>=2"),
        ]

    def test_install_commands(self):
        reqs = PythonEnvironment(pip_requirements=["foo", "bar>=2"])
        commands = reqs.install_commands()
        assert commands == [["pip", "install", "foo", "bar>=2"]]

    def test_install_commands_empty(self):
        reqs = PythonEnvironment(pip_requirements=[])
        commands = reqs.install_commands()
        assert commands == []
