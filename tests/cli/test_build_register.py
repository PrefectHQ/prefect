import json
import os
import pathlib
import textwrap
import threading
from unittest.mock import MagicMock

import box
import pytest
from click.testing import CliRunner

from prefect import Flow
from prefect.cli import cli
from prefect.cli.build_register import (
    TerminalError,
    watch_for_changes,
    load_flows_from_script,
    load_flows_from_module,
    load_flows_from_json,
    build_and_register,
    get_project_id,
    register_serialized_flow,
    expand_paths,
)
from prefect.engine.results import LocalResult
from prefect.run_configs import UniversalRun
from prefect.storage import S3, Local, Module
from prefect.utilities.graphql import GraphQLResult


def test_expand_paths_glob(tmpdir):
    glob_path = str(tmpdir.join("**").join("*.py"))

    expected_paths = [
        pathlib.Path(tmpdir) / "a.py",
        pathlib.Path(tmpdir) / "foo" / "b.py",
        pathlib.Path(tmpdir) / "bar" / "c.py",
        pathlib.Path(tmpdir) / "foobar" / "baz" / "d.py",
    ]
    other_paths = [
        pathlib.Path(tmpdir) / "a.foo",
        pathlib.Path(tmpdir) / "bar" / "b.bar",
    ]
    for path in expected_paths + other_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    result = expand_paths([glob_path])
    assert set(result) == set(str(path.absolute()) for path in expected_paths)


def test_expand_paths_dir_listing(tmpdir):
    dir_path = str(tmpdir)

    expected_paths = [
        pathlib.Path(tmpdir) / "a.py",
        pathlib.Path(tmpdir) / "b.py",
    ]
    other_paths = [
        pathlib.Path(tmpdir) / "a.foo",
        pathlib.Path(tmpdir) / "bar" / "b.bar",
        pathlib.Path(tmpdir) / "foo" / "c.py",
    ]
    for path in expected_paths + other_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    result = expand_paths([dir_path])
    assert set(result) == set(str(path.absolute()) for path in expected_paths)


def test_expand_paths_full_paths(tmpdir):
    paths = [
        pathlib.Path(tmpdir) / "a.py",
        pathlib.Path(tmpdir) / "b.py",
    ]
    other_paths = [
        pathlib.Path(tmpdir) / "a.foo",
        pathlib.Path(tmpdir) / "bar" / "b.bar",
        pathlib.Path(tmpdir) / "foo" / "c.py",
    ]
    for path in paths + other_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    result = expand_paths([str(path.absolute()) for path in paths])
    assert set(result) == set(str(path.absolute()) for path in paths)


class TestWatchForChanges:
    def test_errors_path_does_not_exist(self, tmpdir):
        missing = str(tmpdir.join("not-real"))
        with pytest.raises(TerminalError) as exc:
            for _, _ in watch_for_changes(paths=[missing]):
                assert False, "Should never get here"

        assert repr(missing) in str(exc.value)

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
            pathlib.Path(path3).touch()
            pathlib.Path(path4).touch()
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


@pytest.fixture
def mock_get_project_id(monkeypatch):
    get_project_id = MagicMock()
    get_project_id.return_value = "my-project-id"
    monkeypatch.setattr("prefect.cli.build_register.get_project_id", get_project_id)
    return get_project_id


class TestRegister:
    @pytest.mark.parametrize("exists", [True, False])
    def test_get_project_id(self, exists):
        client = MagicMock()
        if exists:
            client.graphql.return_value = GraphQLResult(
                {"data": {"project": [{"id": "my-project-id"}]}}
            )
        else:
            client.graphql.return_value = GraphQLResult({"data": {"project": []}})

        if exists:
            assert get_project_id(client, "my-project") == "my-project-id"
        else:
            with pytest.raises(
                TerminalError, match="Project 'my-project' does not exist"
            ):
                get_project_id(client, "my-project")

    @pytest.mark.parametrize(
        "already_exists, is_new_version, force, exp_version",
        [
            (False, True, False, 1),
            (False, True, True, 1),
            (True, False, False, 1),
            (True, True, False, 2),
            (True, True, True, 2),
        ],
    )
    def test_register_serialized_flow(
        self, already_exists, is_new_version, force, exp_version
    ):
        client = MagicMock()
        client.graphql.side_effect = responses = []
        if already_exists:
            responses.append(
                GraphQLResult({"data": {"flow": [{"id": "old-id", "version": 1}]}})
            )
        else:
            responses.append(GraphQLResult({"data": {"flow": []}}))

        exp_id = "new-id" if is_new_version else "old-id"
        responses.append(
            GraphQLResult(
                {"data": {"create_flow_from_compressed_string": {"id": exp_id}}}
            )
        )

        serialized_flow = Flow("testing").serialize(build=False)

        flow_id, flow_version, is_new = register_serialized_flow(
            client, serialized_flow, "my-project-id", force
        )

        assert flow_id == exp_id
        assert flow_version == exp_version
        assert is_new == is_new_version

    @pytest.mark.parametrize("schedule", [True, False])
    def test_register_serialized_flow_toggle_schedule(self, schedule):
        client = MagicMock()
        client.graphql.side_effect = [
            GraphQLResult({"data": {"flow": []}}),
            GraphQLResult(
                {"data": {"create_flow_from_compressed_string": {"id": "id"}}}
            ),
        ]

        serialized_flow = Flow("testing").serialize(build=False)

        register_serialized_flow(
            client, serialized_flow, "my-project-id", schedule=schedule
        )

        assert (
            client.graphql.call_args[1]["variables"]["input"]["set_schedule_active"]
            == schedule
        )

    @pytest.mark.parametrize("relative", [False, True])
    def test_load_flows_from_script(self, tmpdir, relative):
        abs_path = str(tmpdir.join("test.py"))
        if relative:
            if os.name == "nt":
                pytest.skip(
                    "This test can fail on windows if the test file is on a different "
                    "drive. This should have no effect during actual execution."
                )
            path = os.path.relpath(abs_path)
        else:
            path = abs_path

        source = textwrap.dedent(
            """
            from prefect import Flow
            from prefect.storage import S3
            from my_prefect_helper_file import helper
            f1 = Flow("f1")
            f1.storage = S3("my-bucket", key="my-key", stored_as_script=True)
            f2 = Flow("f2")

            assert __file__.endswith("test.py")
            assert __name__ != "__main__"
            """
        )
        with open(abs_path, "w") as f:
            f.write(source)

        tmpdir.join("my_prefect_helper_file.py").write("def helper():\n    pass")

        flows = {f.name: f for f in load_flows_from_script(path)}
        assert len(flows) == 2
        assert isinstance(flows["f1"].storage, S3)
        assert flows["f1"].storage.local_script_path == abs_path
        assert isinstance(flows["f2"].storage, Local)
        assert flows["f2"].storage.path == abs_path
        assert flows["f2"].storage.stored_as_script

    def test_load_flows_from_script_error(self, tmpdir, capsys):
        path = str(tmpdir.join("test.py"))
        with open(path, "w") as f:
            f.write("raise ValueError('oh no!')")

        with pytest.raises(TerminalError):
            load_flows_from_script(path)

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
            TerminalError,
            match="module 'mymodule1' has no attribute 'submodule'",
        ):
            load_flows_from_module("mymodule1.submodule")

        with pytest.raises(TerminalError):
            load_flows_from_module("mymodule2")

        out, _ = capsys.readouterr()
        assert "oh no!" in out
        assert "Error loading 'mymodule2'" in out

    def test_load_flows_from_json(self, monkeypatch):
        flows = [
            Flow("flow 1").serialize(build=False),
            Flow("flow 2").serialize(build=False),
        ]
        data = json.dumps({"version": 1, "flows": flows}).encode("utf-8")
        monkeypatch.setattr(
            "prefect.cli.build_register.read_bytes_from_path",
            MagicMock(return_value=data),
        )
        res = load_flows_from_json("https://some/url/flows.json")
        assert res == flows

    def test_load_flows_from_json_fail_read(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "prefect.cli.build_register.read_bytes_from_path",
            MagicMock(side_effect=ValueError("oh no!")),
        )
        with pytest.raises(TerminalError):
            load_flows_from_json("https://some/url/flows.json")

        out, _ = capsys.readouterr()
        assert "Error loading 'https://some/url/flows.json'" in out
        assert "oh no!" in out

    def test_load_flows_from_json_schema_error(self, monkeypatch):
        monkeypatch.setattr(
            "prefect.cli.build_register.read_bytes_from_path",
            MagicMock(return_value=json.dumps({"bad": "file"})),
        )
        with pytest.raises(
            TerminalError, match="is not a valid Prefect flows `json` file."
        ):
            load_flows_from_json("https://some/url/flows.json")

    def test_load_flows_from_json_unsupported_version(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "prefect.cli.build_register.read_bytes_from_path",
            MagicMock(return_value=json.dumps({"version": 2, "flows": []})),
        )
        with pytest.raises(TerminalError, match="is version 2, only version 1"):
            load_flows_from_json("https://some/url/flows.json")

    @pytest.mark.parametrize("force", [False, True])
    def test_build_and_register(self, capsys, monkeypatch, force):
        """Build and register a few flows:
        - 1 new flow
        - 1 updated flow
        - 1 skipped flow
        - 1 error during registration
        - 2 sharing the same storage (which fails to build properly)
        - 2 from a pre-built JSON file
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
        register_serialized_flow = MagicMock()
        register_serialized_flow.side_effect = [
            ("new-id-1", 1, True),
            ("old-id-2", 2, False),
            ("new-id-3", 3, True),
            ValueError("Oh no!"),
            ("new-id-7", 1, True),
            ("old-id-8", 2, False),
        ]
        monkeypatch.setattr(
            "prefect.cli.build_register.register_serialized_flow",
            register_serialized_flow,
        )

        storage1 = MyModule("testing")
        storage1.result = LocalResult()
        flow1 = Flow("flow 1", storage=storage1, run_config=UniversalRun(labels=["a"]))
        flow2 = Flow(
            "flow 2",
            storage=MyModule("testing"),
            run_config=UniversalRun(labels=["a"]),
        )
        storage2 = MyModule("testing")
        flow3 = Flow("flow 3", storage=storage2)
        flow4 = Flow("flow 4", storage=storage2)
        storage3 = BadStorage("testing")
        flow5 = Flow("flow 5", storage=storage3)
        flow6 = Flow("flow 6", storage=storage3)
        flow7 = box.Box(
            Flow("flow 7", run_config=UniversalRun(labels=["a"])).serialize(build=False)
        )
        flow8 = box.Box(
            Flow("flow 8", run_config=UniversalRun(labels=["a"])).serialize(build=False)
        )
        flows = [flow1, flow2, flow3, flow4, flow5, flow6, flow7, flow8]

        stats = build_and_register(
            client, flows, "my-project-id", labels=["b", "c"], force=force
        )

        # 3 calls (one for each unique `MyModule` storage object)
        assert build_call_count == 3

        # 6 register calls (8 - 2 that failed to build storage)
        assert register_serialized_flow.call_count == 6
        for flow, (args, kwargs) in zip(flows, register_serialized_flow.call_args_list):
            assert not args
            assert kwargs["client"] is client
            assert kwargs["serialized_flow"]
            assert kwargs["project_id"] == "my-project-id"
            assert kwargs["force"] == force

        # Stats are recorded properly
        assert dict(stats) == {"registered": 3, "skipped": 2, "errored": 3}

        # Flows are properly configured
        assert flow1.result is storage1.result
        assert flow1.run_config.labels == {"a", "b", "c"}
        assert flow2.run_config.labels == {"a", "b", "c"}
        assert isinstance(flow3.run_config, UniversalRun)
        assert flow3.run_config.labels == {"b", "c"}
        assert isinstance(flow4.run_config, UniversalRun)
        assert flow4.run_config.labels == {"b", "c"}
        assert set(flow7["run_config"]["labels"]) == {"a", "b", "c"}
        assert set(flow8["run_config"]["labels"]) == {"a", "b", "c"}

        # The output contains a traceback, which will vary between machines
        # We only check that the following fixed sections exist in the output
        parts = [
            (
                "  Building `MyModule` storage...\n"
                "  Registering 'flow 1'... Done\n"
                "  └── ID: new-id-1\n"
                "  └── Version: 1\n"
                "  Building `MyModule` storage...\n"
                "  Registering 'flow 2'... Skipped (metadata unchanged)\n"
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
                "  Registering 'flow 7'... Done\n"
                "  └── ID: new-id-7\n"
                "  └── Version: 1\n"
                "  Registering 'flow 8'... Skipped (metadata unchanged)\n"
            ),
        ]
        out, err = capsys.readouterr()
        assert not err
        for part in parts:
            assert part in out

    @pytest.mark.parametrize("force", [False, True])
    @pytest.mark.parametrize("names", [[], ["flow 1"]])
    @pytest.mark.parametrize("schedule", [True, False])
    def test_register_cli(
        self, tmpdir, monkeypatch, mock_get_project_id, force, names, schedule
    ):
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

        register_serialized_flow = MagicMock()
        register_serialized_flow.side_effect = [
            ("new-id-1", 1, True),
            ("old-id-2", 2, False),
        ]
        monkeypatch.setattr(
            "prefect.cli.build_register.register_serialized_flow",
            register_serialized_flow,
        )

        cmd = ["register", "--project", "testing", "--path", path, "-l", "a", "-l", "b"]
        if force:
            cmd.append("--force")
        for name in names:
            cmd.extend(["--name", name])
        if not schedule:
            cmd.append("--no-schedule")
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 0
        if not names:
            names = ["flow 1", "flow 2"]

        storage_labels = Local().labels

        assert register_serialized_flow.call_count == len(names)
        for args, kwargs in register_serialized_flow.call_args_list:
            assert not args
            assert kwargs["project_id"] == "my-project-id"
            assert kwargs["serialized_flow"]["name"] in names
            assert set(kwargs["serialized_flow"]["run_config"]["labels"]) == {
                "a",
                "b",
                *storage_labels,
            }
            assert kwargs["force"] == force
            assert kwargs["schedule"] == schedule

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

    def test_register_cli_name_not_found(self, tmpdir, mock_get_project_id):
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

    def test_register_cli_path_not_found(self, tmpdir, mock_get_project_id):
        path = str(tmpdir.join("test.py"))
        cmd = ["register", "--project", "testing", "-p", path]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1
        assert result.stdout == f"Path {path!r} doesn't exist\n"

    def test_register_cli_json_path_not_found(self, tmpdir, mock_get_project_id):
        path = str(tmpdir.join("test.json"))
        cmd = ["register", "--project", "testing", "-j", path]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1
        assert f"Path {path!r} doesn't exist" in result.stdout

    def test_register_cli_module_not_found(self, mock_get_project_id):
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

    def test_register_cli_project_not_found(self, monkeypatch):
        client = MagicMock()
        client.graphql.return_value = GraphQLResult({"data": {"project": []}})
        monkeypatch.setattr("prefect.Client", MagicMock(return_value=client))
        cmd = [
            "register",
            "--project",
            "testing",
            "-m",
            "a_highly_unlikely_module_name",
        ]
        result = CliRunner().invoke(cli, cmd)
        assert result.exit_code == 1
        assert result.stdout == "Project 'testing' does not exist\n"


class TestBuild:
    def test_build_path_not_found(self, tmpdir):
        path = str(tmpdir.join("test.py"))
        cmd = ["build", "-p", path]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1
        assert f"Path {path!r} doesn't exist" in result.stdout

    def test_build_module_not_found(self):
        cmd = ["build", "-m", "a_highly_unlikely_module_name"]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1
        assert result.stdout == (
            "Collecting flows...\n" "No module named 'a_highly_unlikely_module_name'\n"
        )

    @pytest.mark.parametrize("filter_names", [False, True])
    @pytest.mark.parametrize("update", [False, True])
    def test_build(self, tmpdir, filter_names, update):
        path = str(tmpdir.join("test.py"))
        source = textwrap.dedent(
            """
            from prefect import Flow
            from prefect.run_configs import LocalRun

            flow1 = Flow("flow 1")
            flow2 = Flow("flow 2", run_config=LocalRun(labels=["new"]))
            """
        )
        with open(path, "w") as f:
            f.write(source)

        out_path = str(tmpdir.join("flows.json"))

        if update:
            orig_flows = [
                Flow("flow 2", run_config=UniversalRun(labels=["orig"])),
                Flow("flow 3"),
            ]
            orig = {
                "version": 1,
                "flows": [f.serialize(build=False) for f in orig_flows],
            }
            with open(out_path, "w") as f:
                json.dump(orig, f)

        cmd = ["build", "--path", path, "-l", "a", "-l", "b", "-o", out_path]
        if filter_names:
            cmd.extend(["--name", "flow 2"])
        if update:
            cmd.append("--update")
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 0

        with open(out_path, "rb") as f:
            out = json.load(f)

        assert out["version"] == 1
        assert out["flows"]

        if filter_names:
            build_names = ["flow 2"]
            flow2 = out["flows"][0]
        else:
            build_names = ["flow 1", "flow 2"]
            flow2 = out["flows"][1]
        exp_names = build_names + ["flow 3"] if update else build_names
        written_names = [f["name"] for f in out["flows"]]
        assert written_names == exp_names

        storage_labels = Local().labels
        assert set(flow2["run_config"]["labels"]) == {"a", "b", "new", *storage_labels}
        assert flow2["run_config"]["type"] == "LocalRun"

        build_logs = "\n".join(
            f"  Building `Local` storage...\n  Building '{name}'... Done"
            for name in build_names
        )
        out = (
            f"Collecting flows...\n"
            f"Processing {path!r}:\n"
            f"{build_logs}\n"
            f"Writing output to {out_path!r}\n"
            f"========================== {len(build_names)} built ==========================\n"
        )
        assert result.stdout == out

    def test_build_storage_error(self, tmpdir):
        path = str(tmpdir.join("test.py"))
        source = textwrap.dedent(
            """
            from prefect import Flow
            from prefect.storage import Module

            class BadModule(Module):
                def build(self):
                    raise ValueError('oh no!')

            flow1 = Flow("flow 1")
            flow2 = Flow("flow 2", storage=BadModule('testing'))
            """
        )
        with open(path, "w") as f:
            f.write(source)

        out_path = str(tmpdir.join("flows.json"))

        cmd = ["build", "--path", path, "-o", out_path]
        result = CliRunner().invoke(cli, cmd)

        assert result.exit_code == 1

        with open(out_path, "rb") as f:
            out = json.load(f)

        assert out["version"] == 1
        assert out["flows"]

        assert "Building 'flow 1'... Done\n" in result.stdout
        assert "oh no!" in result.stdout
        assert (
            "===================== 1 built, 1 errored =====================\n"
            in result.stdout
        )
