import os
import threading
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from prefect.cli import cli
from prefect.cli.register import TerminalError, watch_for_changes


def test_register_flow_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["register", "flow", "--help"])
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
        "register",
        "flow",
        "--file",
        full_path,
        "--name",
        "test-flow",
        "--project",
        "project",
        "--skip-if-flow-metadata-unchanged",
    ]
    for l in labels:
        args.extend(["-l", l])

    runner = CliRunner()
    result = runner.invoke(cli, args)
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


class TestWatchForChanges:
    def test_errors_path_does_not_exist(self, tmpdir):
        missing = str(tmpdir.join("not-real"))
        with pytest.raises(TerminalError, match=missing):
            for _, _ in watch_for_changes(paths=[missing]):
                assert False, "Should never get here"

    def test_errors_module_does_not_exist(self):
        name = "not_a_real_module_name"
        with pytest.raises(TerminalError, match=name):
            for _, _ in watch_for_changes(modules=[name]):
                assert False, "Should never get here"

    def test_watch_paths(self, tmpdir):
        dir_path = str(tmpdir.join("dir").mkdir())
        path1 = str(tmpdir.join("test1.py").ensure(file=True))
        path2 = str(tmpdir.join("test2.py").ensure(file=True))
        path3 = os.path.join(dir_path, "test3.py")
        path4 = os.path.join(dir_path, "test4.something")

        iterator = watch_for_changes(paths=[dir_path, path1, path2], period=0.1)

        # Initial iteration hits all known paths
        paths, mods = next(iterator)
        assert not mods
        assert set(paths) == {path1, path2}

        # Later iterations only yield paths that are new or changed
        def update():
            with open(path3, "wb"):
                pass
            with open(path4, "wb"):
                pass
            os.utime(path1)

        timer = threading.Timer(0.15, update)
        timer.start()

        paths, mods = next(iterator)
        # path4 isn't included, since only `*.py` files are watched
        assert set(paths) == {path1, path3}

        # Deleting some original paths causes no errors
        os.remove(path1)
        os.remove(path3)
        timer = threading.Timer(0.15, lambda: os.utime(path2))
        timer.start()

        paths, mods = next(iterator)
        assert set(paths) == {path2}

        # If those paths are readded, next iteration picks them up
        with open(path1, "wb"):
            pass
        os.utime(path2)
        paths, mods = next(iterator)
        assert set(paths) == {path1, path2}

    def test_watch_modules(self, tmpdir, monkeypatch):
        mod1 = tmpdir.join("module1.py").ensure(file=True)
        mod2 = tmpdir.join("module2.py").ensure(file=True)
        monkeypatch.syspath_prepend(str(tmpdir))

        iterator = watch_for_changes(modules=["module1", "module2"], period=0.1)

        # Initial iteration hits all known modules
        paths, mods = next(iterator)
        assert not paths
        assert set(mods) == {"module1", "module2"}

        # Later iterations only yield modules that are new or changed
        timer = threading.Timer(0.15, lambda: mod1.setmtime())
        timer.start()

        paths, mods = next(iterator)
        assert not paths
        assert set(mods) == {"module1"}

        # Deleting some original modules causes no errors
        mod1.remove()
        timer = threading.Timer(0.15, mod2.setmtime)
        timer.start()
        paths, mods = next(iterator)
        assert set(mods) == {"module2"}

        # If those modules are readded, next iteration picks them up
        mod1.ensure(file=True)
        mod2.setmtime()
        paths, mods = next(iterator)
        assert set(mods) == {"module1", "module2"}
