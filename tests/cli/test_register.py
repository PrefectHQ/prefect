import os
import threading
import textwrap
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from prefect import Flow
from prefect.cli import cli
from prefect.cli.register import (
    TerminalError,
    watch_for_changes,
    load_flows_from_path,
    load_flows_from_module,
    build_and_register,
)
from prefect.engine.results import LocalResult
from prefect.environments.execution import LocalEnvironment
from prefect.run_configs import UniversalRun
from prefect.storage import S3, Local, Module
from prefect.utilities.graphql import GraphQLResult


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

    assert "Warning: `prefect register flow` is deprecated" in result.stdout
    assert result.exit_code == 0


def register_flow_errors_if_pass_options_to_register_group():
    """Since we deprecated a subcommand, we need to manually check that
    subcommand options are valid"""
    result = CliRunner().invoke(
        cli, ["register", "--project", "my-project", "flow", "--file", "some_path.py"]
    )
    assert result.exit_code == 1
    assert "Got unexpected extra argument (flow)" in result.stdout


class TestWatchForChanges:
    def test_errors_path_does_not_exist(self, tmpdir):
        missing = str(tmpdir.join("not-real"))
        with pytest.raises(TerminalError) as exc:
            for _, _ in watch_for_changes(paths=[missing]):
                assert False, "Should never get here"

        assert missing in str(exc)

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


class TestRegister:
    def test_load_flows_from_path(self, tmpdir):
        path = str(tmpdir.join("test.py"))
        source = textwrap.dedent(
            """
            from prefect import Flow
            from prefect.storage import S3
            f1 = Flow("f1")
            f1.storage = S3("my-bucket", key="my-key", stored_as_script=True)
            f2 = Flow("f2")
            """
        )
        with open(path, "w") as f:
            f.write(source)

        flows = {f.name: f for f in load_flows_from_path(path)}
        assert len(flows) == 2
        assert isinstance(flows["f1"].storage, S3)
        assert flows["f1"].storage.local_script_path == path
        assert isinstance(flows["f2"].storage, Local)
        assert flows["f2"].storage.path == path
        assert flows["f2"].storage.stored_as_script

    def test_load_flows_from_path_error(self, tmpdir, capsys):
        path = str(tmpdir.join("test.py"))
        with open(path, "w") as f:
            f.write("raise ValueError('oh no!')")

        with pytest.raises(TerminalError):
            load_flows_from_path(path)

        out, _ = capsys.readouterr()
        assert "oh no!" in out
        assert repr(path) in out

    def test_load_flows_from_module(self, tmpdir, monkeypatch):
        monkeypatch.syspath_prepend(str(tmpdir))
        source = textwrap.dedent(
            """
            from prefect import Flow
            from prefect.storage import Module
            f1 = Flow("f1")
            f1.storage = Module("mymodule.submodule")
            f2 = Flow("f2")
            """
        )
        path = tmpdir.join("mymodule.py")
        path.write(source)

        flows = {f.name: f for f in load_flows_from_module("mymodule")}
        assert len(flows) == 2
        assert isinstance(flows["f1"].storage, Module)
        assert flows["f1"].storage.module == "mymodule.submodule"
        assert isinstance(flows["f2"].storage, Module)
        assert flows["f2"].storage.module == "mymodule"

    def test_load_flows_from_module_not_found_error(self, tmpdir, monkeypatch, capsys):
        monkeypatch.syspath_prepend(str(tmpdir))
        tmpdir.join("mymodule1.py").ensure(file=True)
        tmpdir.join("mymodule2.py").write("raise ValueError('oh no!')")

        with pytest.raises(TerminalError, match="No module named 'mymodule3'"):
            load_flows_from_module("mymodule3")

        with pytest.raises(TerminalError, match="No module named 'mymodule3'"):
            load_flows_from_module("mymodule3.submodule")

        with pytest.raises(
            TerminalError, match="No module named 'mymodule1.submodule'"
        ):
            load_flows_from_module("mymodule1.submodule")

        with pytest.raises(TerminalError):
            load_flows_from_module("mymodule2")

        out, _ = capsys.readouterr()
        assert "oh no!" in out
        assert "Error loading 'mymodule2'" in out

    @pytest.mark.parametrize("force", [False, True])
    def test_build_and_register(self, capsys, monkeypatch, force):
        """Build and register a few flows:
        - 1 new flow
        - 1 updated flow
        - 1 skipped flow
        - 1 error during registration
        - 2 sharing the same storage (which fails to build properly)
        """
        build_call_count = 0

        class MyModule(Module):
            def build(self):
                nonlocal build_call_count
                build_call_count += 1

        class BadStorage(Module):
            def build(self):
                raise ValueError("whoops!")

        client = MagicMock()
        client.graphql.side_effect = [
            GraphQLResult({"data": {"flow": []}}),
            GraphQLResult({"data": {"flow": [{"id": "old-id-2", "version": 1}]}}),
            GraphQLResult({"data": {"flow": [{"id": "old-id-3", "version": 2}]}}),
            GraphQLResult({"data": {"flow": [{"id": "old-id-4", "version": 3}]}}),
        ]
        client.register.side_effect = [
            "new-id-1",
            "old-id-2",
            "new-id-3",
            ValueError("Oh no!"),
        ]

        storage1 = MyModule("testing")
        storage1.result = LocalResult()
        flow1 = Flow("flow 1", storage=storage1, run_config=UniversalRun(labels=["a"]))
        flow2 = Flow(
            "flow 2",
            storage=MyModule("testing"),
            environment=LocalEnvironment(labels=["a"]),
        )
        storage2 = MyModule("testing")
        flow3 = Flow("flow 3", storage=storage2)
        flow4 = Flow("flow 4", storage=storage2)
        storage3 = BadStorage("testing")
        flow5 = Flow("flow 5", storage=storage3)
        flow6 = Flow("flow 6", storage=storage3)
        flows = [flow1, flow2, flow3, flow4, flow5, flow6]

        stats = build_and_register(
            client, flows, "testing", labels=["b", "c"], force=force
        )

        # 3 calls (one for each unique `MyModule` storage object)
        assert build_call_count == 3

        # 4 register calls (6 - 2 that failed to build storage)
        assert client.register.call_count == 4
        for flow, (args, kwargs) in zip(flows, client.register.call_args_list):
            assert not args
            assert kwargs["flow"] is flow
            assert kwargs["project_name"] == "testing"
            assert kwargs["build"] is False
            assert kwargs["no_url"] is True
            if force:
                assert kwargs["idempotency_key"] is None
            else:
                assert kwargs["idempotency_key"]

        # Stats are recorded properly
        assert dict(stats) == {"registered": 2, "skipped": 1, "errored": 3}

        # Flows are properly configured
        assert flow1.result is storage1.result
        assert flow1.run_config.labels == {"a", "b", "c"}
        assert flow2.environment.labels == {"a", "b", "c"}
        assert isinstance(flow3.run_config, UniversalRun)
        assert flow3.run_config.labels == {"b", "c"}
        assert isinstance(flow4.run_config, UniversalRun)
        assert flow4.run_config.labels == {"b", "c"}

        # The output contains a traceback, which will vary between machines
        # We only check that the following fixed sections exist in the output
        parts = [
            (
                "  Building `MyModule` storage...\n"
                "  Registering 'flow 1'... Done\n"
                "  └── ID: new-id-1\n"
                "  └── Version: 1\n"
                "  Building `MyModule` storage...\n"
                "  Registering 'flow 2'... Skipped\n"
                "  Building `MyModule` storage...\n"
                "  Registering 'flow 3'... Done\n"
                "  └── ID: new-id-3\n"
                "  └── Version: 3\n"
                "  Registering 'flow 4'... Error\n"
                "    Traceback (most recent call last):\n"
            ),
            (
                "    ValueError: Oh no!\n"
                "\n"
                "  Building `BadStorage` storage...\n"
                "    Error building storage:\n"
                "      Traceback (most recent call last):\n"
            ),
            (
                "      ValueError: whoops!\n"
                "\n"
                "  Registering 'flow 5'... Error\n"
                "  Registering 'flow 6'... Error\n"
            ),
        ]
        out, err = capsys.readouterr()
        assert not err
        for part in parts:
            assert part in out

    @pytest.mark.parametrize("force", [False, True])
    @pytest.mark.parametrize("names", [[], ["flow 1"]])
    def test_register_cli(self, tmpdir, monkeypatch, force, names):
        path = str(tmpdir.join("test.py"))
        source = textwrap.dedent(
            """
            from prefect import Flow

            flow1 = Flow("flow 1")
            flow2 = Flow("flow 2")
            """
        )
        with open(path, "w") as f:
            f.write(source)

        client = MagicMock()
        client.graphql.side_effect = [
            GraphQLResult({"data": {"flow": []}}),
            GraphQLResult({"data": {"flow": [{"id": "old-id-2", "version": 1}]}}),
        ]
        client.register.side_effect = ["new-id-1", "old-id-2"]
        monkeypatch.setattr("prefect.Client", MagicMock(return_value=client))

        cmd = ["register", "--project", "testing", "--path", path, "-l", "a", "-l", "b"]
        if force:
            cmd.append("--force")
        for name in names:
            cmd.extend(["--name", name])
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 0
        if not names:
            names = ["flow 1", "flow 2"]

        assert client.register.call_count == len(names)
        for args, kwargs in client.register.call_args_list:
            assert not args
            assert kwargs["project_name"] == "testing"
            assert kwargs["flow"].name in names
            assert kwargs["flow"].run_config.labels == {"a", "b"}
            if force:
                assert kwargs["idempotency_key"] is None
            else:
                assert kwargs["idempotency_key"]

        # Bulk of the output is tested elsewhere, only a few smoketests here
        assert "Building `Local` storage..." in result.stdout
        assert repr(path) in result.stdout
        if len(names) == 2:
            assert (
                "================== 1 registered, 1 skipped =================="
                in result.stdout
            )
        else:
            assert (
                "======================== 1 registered ========================"
                in result.stdout
            )

    def test_register_cli_name_not_found(self, tmpdir):
        path = str(tmpdir.join("test.py"))
        source = textwrap.dedent(
            """
            from prefect import Flow

            flow1 = Flow("flow 1")
            flow2 = Flow("flow 2")
            """
        )
        with open(path, "w") as f:
            f.write(source)

        cmd = [
            "register",
            "--project",
            "testing",
            "-p",
            path,
            "-n",
            "flow 1",
            "-n",
            "flow 3",
        ]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1
        assert result.stdout == (
            "Collecting flows...\n" "Failed to find the following flows:\n" "- flow 3\n"
        )

    def test_register_cli_path_not_found(self, tmpdir):
        path = str(tmpdir.join("test.py"))
        cmd = ["register", "--project", "testing", "-p", path]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1
        assert result.stdout == f"Path {path!r} doesn't exist\n"

    def test_register_cli_module_not_found(self):
        cmd = [
            "register",
            "--project",
            "testing",
            "-m",
            "a_highly_unlikely_module_name",
        ]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1
        assert result.stdout == (
            "Collecting flows...\n" "No module named 'a_highly_unlikely_module_name'\n"
        )

    def test_register_cli_no_project_specified(self):
        result = CliRunner().invoke(cli, ["register", "-p", "some_path"])
        assert result.exit_code == 1
        assert result.stdout == "Error: Missing required option '--project'\n"
