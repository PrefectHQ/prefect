import sys
from contextlib import nullcontext
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from prefect.software.conda import (
    CONDA_REQUIREMENT,
    CondaEnvironment,
    CondaError,
    CondaRequirement,
    current_environment_conda_requirements,
)
from prefect.software.pip import PipRequirement

CONDA_REQUIREMENT_TEST_CASES = [
    ("x", {"name": "x"}),
    ("x=", None),
    ("x=1", {"name": "x", "version_specifier": "=1", "version": "1"}),
    ("x>=1", {"name": "x", "version_specifier": ">=1", "version": "1"}),
    ("x>1", {"name": "x", "version_specifier": ">1", "version": "1"}),
    ("x=1.2.3", {"name": "x", "version_specifier": "=1.2.3", "version": "1.2.3"}),
    ("x=1.2b1", {"name": "x", "version_specifier": "=1.2b1", "version": "1.2b1"}),
    ("x=1.2b1=", None),
    (
        "x=1.2b1=ashfa_0",
        {
            "name": "x",
            "version_specifier": "=1.2b1",
            "version": "1.2b1",
            "build_specifier": "=ashfa_0",
            "build": "ashfa_0",
        },
    ),
]


CONDA_ENV_NOT_ACTIVATED_JSON = r"""
{
  "caused_by": "None",
  "error": "CondaEnvException: Unable to determine environment\n\nPlease re-run this command with one of the following options:\n\n* Provide an environment name via --name or -n\n* Re-run this command inside an activated conda environment.",
  "exception_name": "CondaEnvException",
  "exception_type": "<class 'conda_env.exceptions.CondaEnvException'>",
  "message": "Unable to determine environment\n\nPlease re-run this command with one of the following options:\n\n* Provide an environment name via --name or -n\n* Re-run this command inside an activated conda environment."
}
"""


CONDA_ENV_EXPORT_SIMPLE_JSON = r"""
{
  "channels": [
    "defaults"
  ],
  "dependencies": [
    "python=3.8",
    "sqlite==3.31.1",
    "certifi"
  ],
  "name": "flirty-crocodile",
  "prefix": "/opt/homebrew/Caskroom/miniconda/base/envs/flirty-crocodile"
}
"""

CONDA_ENV_EXPORT_WITH_BUILDS_JSON = r"""
{
  "channels": [
    "defaults"
  ],
  "dependencies": [
    "certifi=2022.5.18.1=py38hecd8cb5_0",
    "python=3.8.3=h26836e1_1",
    "sqlite=3.31.1=h5c1f38d_1"
  ],  
  "name": "flirty-crocodile",
  "prefix": "/opt/homebrew/Caskroom/miniconda/base/envs/flirty-crocodile"
}
"""

CONDA_ENV_EXPORT_WITH_PIP_JSON = r"""
{
  "channels": [
    "defaults"
  ],
  "dependencies": [
    "python=3.8",
    "sqlite==3.31.1",
    "certifi",
    {
      "pip": [
        "aiofiles==0.8.0",
        "aiohttp==3.8.1",
        "aiohttp-cors==0.7.0",
        "aiosignal==1.2.0",
        "aiosqlite==0.17.0"
      ]
    }
  ],
  "name": "flirty-crocodile",
  "prefix": "/opt/homebrew/Caskroom/miniconda/base/envs/flirty-crocodile"
}
"""


@pytest.fixture
def mock_conda_process(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("subprocess.run", mock)
    yield mock


@pytest.mark.parametrize(
    "input,expected",
    CONDA_REQUIREMENT_TEST_CASES,
)
def test_parsing(input, expected):
    result = CONDA_REQUIREMENT.match(input)
    if expected is None:
        assert (
            result is None
        ), f"Input {input!r} should not be valid, matched {result.groups()}"
    else:
        assert result is not None

        groups = result.groupdict()
        for key, value in tuple(groups.items()):
            if key not in expected:
                assert value is None, f"{key!r} should not have a match."
                groups.pop(key)

        assert groups == expected


class TestCondaRequirement:
    @pytest.mark.parametrize(
        "input,expected",
        CONDA_REQUIREMENT_TEST_CASES,
    )
    def test_init(self, input, expected):
        raises_on_bad_match = (
            pytest.raises(ValueError, match="Invalid requirement")
            if expected is None
            else nullcontext()
        )

        with raises_on_bad_match:
            requirement = CondaRequirement(input)

        if expected:
            for key, value in expected.items():
                assert getattr(requirement, key) == value

    def test_to_string_is_original(self):
        assert str(CondaRequirement("x=1.2")) == "x=1.2"

    def test_equality(self):
        assert CondaRequirement("x=1.2") == CondaRequirement("x=1.2")

    def test_inequality(self):
        assert CondaRequirement("x") != CondaRequirement("x=1.2")


class TestCurrentEnvironmentCondaRequirements:
    @pytest.mark.service("environment")
    @pytest.mark.parametrize(
        "options", [{}, {"include_builds": True}, {"explicit_only": False}]
    )
    def test_unmocked_retrieval_succeeds(self, options):
        # Check that we actually parsed environment errors correctly on systems without
        # conda
        raises = (
            pytest.raises(CondaError)
            if "conda" not in sys.executable
            else nullcontext()
        )
        with raises as should_raise:
            result = current_environment_conda_requirements(**options)

        if not should_raise:
            assert len(result) > 0
            assert all(isinstance(req, CondaRequirement) for req in result)

    def test_environment_not_activated(self, mock_conda_process):
        mock_conda_process.return_value.stdout = CONDA_ENV_NOT_ACTIVATED_JSON
        with pytest.raises(CondaError, match="Unable to determine environment"):
            current_environment_conda_requirements()

    def test_environment_output(self, mock_conda_process):
        mock_conda_process.return_value.stdout = CONDA_ENV_EXPORT_SIMPLE_JSON
        requirements = current_environment_conda_requirements()
        mock_conda_process.assert_called_once_with(
            ["conda", "env", "export", "--json", "--no-builds", "--from-history"],
            capture_output=True,
        )
        assert requirements == [
            CondaRequirement("python=3.8"),
            CondaRequirement("sqlite==3.31.1"),
            CondaRequirement("certifi"),
        ]

    def test_environment_output_with_builds(self, mock_conda_process):
        mock_conda_process.return_value.stdout = CONDA_ENV_EXPORT_WITH_BUILDS_JSON
        requirements = current_environment_conda_requirements(include_builds=True)
        mock_conda_process.assert_called_once_with(
            ["conda", "env", "export", "--json", "--from-history"],
            capture_output=True,
        )
        assert requirements == [
            CondaRequirement("certifi=2022.5.18.1=py38hecd8cb5_0"),
            CondaRequirement("python=3.8.3=h26836e1_1"),
            CondaRequirement("sqlite=3.31.1=h5c1f38d_1"),
        ]
        assert all(req.build is not None for req in requirements)

    def test_environment_output_with_pip(self, mock_conda_process):
        mock_conda_process.return_value.stdout = CONDA_ENV_EXPORT_WITH_PIP_JSON
        requirements = current_environment_conda_requirements()
        assert requirements == [
            CondaRequirement("python=3.8"),
            CondaRequirement("sqlite==3.31.1"),
            CondaRequirement("certifi"),
        ]


class TestCondaEnvironment:
    def test_init(self):
        reqs = CondaEnvironment(
            pip_requirements=["foo", "bar>=2"],
            conda_requirements=["foobar", "x=1.0=afsfs_x"],
        )
        assert reqs.pip_requirements == [
            PipRequirement("foo"),
            PipRequirement("bar>=2"),
        ]
        assert reqs.conda_requirements == [
            CondaRequirement("foobar"),
            CondaRequirement("x=1.0=afsfs_x"),
        ]

    def test_from_file(self, tmp_path):
        reqs_file = tmp_path / "requirements.txt"
        reqs_file.write_text(
            dedent(
                """
                name: test
                channels:
                - defaults
                dependencies:
                - python=3.7.11
                - readline
                - sqlite=3.37.2=h707629a_0
                - pip:
                    - foo==0.8.0
                    - bar
                prefix: /opt/homebrew/Caskroom/miniconda/base/envs/test
                """
            )
        )

        reqs = CondaEnvironment.from_file(reqs_file)
        assert reqs.pip_requirements == [
            PipRequirement("foo==0.8.0"),
            PipRequirement("bar"),
        ]
        assert reqs.python_version == "3.7.11"
        assert reqs.conda_requirements == [
            CondaRequirement("readline"),
            CondaRequirement("sqlite=3.37.2=h707629a_0"),
        ]

    def test_from_file_unsupported_subtype(self, tmp_path):
        reqs_file = tmp_path / "requirements.txt"
        reqs_file.write_text(
            dedent(
                """
                name: test
                channels:
                - defaults
                dependencies:
                - python=3.7.11
                - readline
                - sqlite=3.37.2=h707629a_0
                - ohno:
                    - foo==0.8.0
                    - bar
                prefix: /opt/homebrew/Caskroom/miniconda/base/envs/test
                """
            )
        )

        with pytest.raises(
            ValueError, match="Found unsupported requirements types in file: 'ohno'"
        ):
            CondaEnvironment.from_file(reqs_file)

    def test_from_file_duplicate_subtype(self, tmp_path):
        reqs_file = tmp_path / "requirements.txt"
        reqs_file.write_text(
            dedent(
                """
                name: test
                channels:
                - defaults
                dependencies:
                - python=3.7.11
                - readline
                - sqlite=3.37.2=h707629a_0
                - pip:
                    - foo==0.8.0
                - pip:
                    - bar
                prefix: /opt/homebrew/Caskroom/miniconda/base/envs/test
                """
            )
        )

        with pytest.raises(
            ValueError,
            match="Invalid conda requirements specification. Found duplicate key 'pip'",
        ):
            CondaEnvironment.from_file(reqs_file)

    def test_install_commands(self):
        reqs = CondaEnvironment(
            pip_requirements=["foo", "bar>=2"],
            conda_requirements=["foobar", "x=1.0=afsfs_x"],
        )

        commands = reqs.install_commands()
        assert commands == [
            "conda install 'foobar' 'x=1.0=afsfs_x'",
            "pip install 'foo' 'bar>=2'",
        ]

    def test_install_commands_empty_pip(self):
        reqs = CondaEnvironment(conda_requirements=["foobar", "x=1.0=afsfs_x"])

        commands = reqs.install_commands()
        assert commands == ["conda install 'foobar' 'x=1.0=afsfs_x'"]

    def test_install_commands_empty_conda(self):
        reqs = CondaEnvironment(pip_requirements=["foo", "bar>=2"])

        commands = reqs.install_commands()
        assert commands == ["pip install 'foo' 'bar>=2'"]
