from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from prefect.cli.register import register


def test_register_init():
    runner = CliRunner()
    result = runner.invoke(register)
    assert result.exit_code == 0
    assert "Register flows" in result.output


def test_register_help():
    runner = CliRunner()
    result = runner.invoke(register, ["--help"])
    assert result.exit_code == 0
    assert "Register flows" in result.output


def test_register_flow_help():
    runner = CliRunner()
    result = runner.invoke(register, ["flow", "--help"])
    assert result.exit_code == 0
    assert "Register a flow" in result.output


@pytest.mark.parametrize("labels", [[], ["b", "c"]])
@pytest.mark.parametrize("kind", ["run_config", "environment", "neither"])
def test_register_flow_call(monkeypatch, tmpdir, kind, labels):
    client = MagicMock()
    monkeypatch.setattr("prefect.Client", MagicMock(return_value=client))

    if kind == "environment":
        contents = (
            "from prefect import Flow\n"
            "from prefect.environments.execution import LocalEnvironment\n"
            "from prefect.storage import Local\n"
            "f = Flow('test-flow', environment=LocalEnvironment(labels=['a']),\n"
            "   storage=Local(add_default_labels=False))"
        )
    elif kind == "run_config":
        contents = (
            "from prefect import Flow\n"
            "from prefect.run_configs import KubernetesRun\n"
            "from prefect.storage import Local\n"
            "f = Flow('test-flow', run_config=KubernetesRun(labels=['a']),\n"
            "   storage=Local(add_default_labels=False))"
        )
    else:
        contents = (
            "from prefect import Flow\n"
            "from prefect.storage import Local\n"
            "f = Flow('test-flow', storage=Local(add_default_labels=False))"
        )

    full_path = str(tmpdir.join("flow.py"))
    with open(full_path, "w") as f:
        f.write(contents)

    args = [
        "flow",
        "--file",
        full_path,
        "--name",
        "test-flow",
        "--project",
        "project",
        "--detect-changes",
    ]
    for l in labels:
        args.extend(["-l", l])

    runner = CliRunner()
    result = runner.invoke(register, args)
    assert client.register.called
    assert client.register.call_args[1]["project_name"] == "project"
    assert client.register.call_args[1]["idempotency_key"] is not None

    # Check additional labels are set if specified
    flow = client.register.call_args[1]["flow"]
    if kind == "run_config":
        assert flow.run_config.labels == {"a", *labels}
    elif kind == "environment":
        assert flow.environment.labels == {"a", *labels}
    else:
        assert flow.run_config.labels == {*labels}

    assert result.exit_code == 0
