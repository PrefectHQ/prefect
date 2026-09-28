import asyncio
import json
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from prefect.deployments.steps.pull import agit_clone, git_clone
from prefect.locking._filelock import FileLock
from prefect.runner.storage import GitRepository


def git(repo: Path, *args: str) -> str:
    return (
        subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)
        .decode()
        .strip()
    )


@pytest.fixture
def source(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "remote"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "payload.txt").write_text("original")
    (repo / ".gitattributes").write_text("payload.txt export-ignore\n")
    (repo / "nested").mkdir()
    (repo / "nested/data.txt").write_text("nested")
    (repo / "other").mkdir()
    (repo / "other/hidden.txt").write_text("other")
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "initial")
    commit = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "-a", "v1", "-m", "release")
    git(repo, "branch", "previous")
    (repo / "payload.txt").write_text("new")
    git(repo, "commit", "--quiet", "-am", "second")
    return repo, commit


def storage(root: Path, repo: Path, name: str, **kwargs) -> GitRepository:
    result = GitRepository(
        url=repo.as_uri(), name=name, cache_dir=root / "cache", **kwargs
    )
    result.set_base_path(root)
    return result


def assert_same_checkout(first: Path, second: Path) -> None:
    for args in (
        ("rev-parse", "HEAD"),
        ("status", "--porcelain"),
        ("ls-files", "--stage"),
        ("rev-parse", "--is-shallow-repository"),
        ("remote", "get-url", "origin"),
    ):
        assert git(first, *args) == git(second, *args)
    paths = git(first, "ls-files").splitlines()
    for path in paths:
        if (first / path).is_file():
            assert (first / path).read_bytes() == (second / path).read_bytes()
    assert not (second / ".git/objects/info/alternates").exists()


@pytest.mark.parametrize("selection", ["default", "branch", "tag", "commit", "short"])
@pytest.mark.parametrize("sparse", [False, True])
async def test_cached_clone_matches_normal_clone(
    tmp_path: Path, source: tuple[Path, str], selection: str, sparse: bool
):
    repo, commit = source
    options = {
        "default": {},
        "branch": {"branch": "previous"},
        "tag": {"branch": "v1"},
        "commit": {"commit_sha": commit},
        "short": {"commit_sha": commit[:8]},
    }[selection]
    if sparse:
        options["directories"] = ["nested"]
    normal = GitRepository(url=repo.as_uri(), name="normal", **options)
    normal.set_base_path(tmp_path)
    if selection == "short":
        with pytest.raises(subprocess.CalledProcessError):
            await normal.pull_code()
        with pytest.raises(subprocess.CalledProcessError):
            await storage(tmp_path, repo, "cached", **options).pull_code()
        return
    await normal.pull_code()
    for name in ("cold", "warm"):
        cached = storage(tmp_path, repo, name, **options)
        await cached.pull_code()
        assert_same_checkout(normal.destination, cached.destination)
        assert (cached.destination / "payload.txt").exists()
        if sparse:
            assert not (cached.destination / "other/hidden.txt").exists()


async def test_branch_and_tags_refresh_and_runs_are_independent(
    tmp_path: Path, source: tuple[Path, str]
):
    repo, _ = source
    first = storage(tmp_path, repo, "first")
    await first.pull_code()
    old_head = git(first.destination, "rev-parse", "HEAD")
    (repo / "payload.txt").write_text("latest")
    git(repo, "commit", "--quiet", "-am", "advance")
    git(repo, "tag", "-a", "v2", "-m", "new release")
    second = storage(tmp_path, repo, "second")
    await second.pull_code()
    assert git(second.destination, "rev-parse", "HEAD") == git(
        repo, "rev-parse", "HEAD"
    )
    assert git(second.destination, "describe") == "v2"
    (first.destination / "payload.txt").write_text("mutated")
    shutil.rmtree(tmp_path / "cache")
    assert git(first.destination, "rev-parse", "HEAD") == old_head
    assert (second.destination / "payload.txt").read_text() == "latest"
    git(second.destination, "fsck", "--full")


async def test_unavailable_remote_does_not_silently_use_stale_cache(
    tmp_path: Path, source: tuple[Path, str]
):
    repo, commit = source
    await storage(tmp_path, repo, "first", commit_sha=commit).pull_code()
    repo.rename(tmp_path / "offline")
    with pytest.raises(RuntimeError):
        await storage(tmp_path, repo, "second", commit_sha=commit).pull_code()
    assert not (tmp_path / "second").exists()
    assert not list((tmp_path / "cache").rglob("staging-*"))


async def test_concurrent_runs_share_one_mirror(
    tmp_path: Path, source: tuple[Path, str]
):
    repo, commit = source
    runs = [storage(tmp_path, repo, f"run-{i}", commit_sha=commit) for i in range(4)]
    await asyncio.gather(*(run.pull_code() for run in runs))
    assert len(list((tmp_path / "cache/prefect-git-v1").iterdir())) == 1
    assert all(git(run.destination, "rev-parse", "HEAD") == commit for run in runs)
    shutil.rmtree(tmp_path / "cache")
    for run in runs:
        git(run.destination, "fsck", "--full")


async def test_byte_budget_eviction_preserves_run(
    tmp_path: Path, source: tuple[Path, str]
):
    repo, _ = source
    run = storage(tmp_path, repo, "first")
    await run.pull_code()
    cache = tmp_path / "cache/prefect-git-v1"
    GitRepository._prune_git_cache(cache, max_bytes=1)
    assert not list(cache.iterdir())
    git(run.destination, "fsck", "--full")


async def test_sync_and_async_steps_share_cache(
    tmp_path: Path, source: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
):
    repo, commit = source
    monkeypatch.chdir(tmp_path)
    kwargs = dict(
        repository=repo.as_uri(), commit_sha=commit, cache_dir=str(tmp_path / "cache")
    )
    sync = await asyncio.to_thread(git_clone, **kwargs, clone_directory_name="sync")
    asynchronous = await agit_clone(**kwargs, clone_directory_name="async")
    assert sync == {"directory": "sync"}
    assert asynchronous == {"directory": "async"}
    assert storage(tmp_path, repo, "roundtrip").to_pull_step()[
        "prefect.deployments.steps.git_clone"
    ]["cache_dir"] == str(tmp_path / "cache")


async def test_submodules_match_normal_clone_after_cache_removal(
    tmp_path: Path, source: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
):
    repo, _ = source
    child = tmp_path / "child"
    child.mkdir()
    git(child, "init", "--quiet")
    git(child, "config", "user.name", "Test")
    git(child, "config", "user.email", "test@example.invalid")
    (child / "child.txt").write_text("child")
    git(child, "add", ".")
    git(child, "commit", "--quiet", "-m", "child")
    git(
        repo,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        child.as_uri(),
        "modules/child",
    )
    git(repo, "commit", "--quiet", "-am", "add submodule")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "always")
    normal = GitRepository(url=repo.as_uri(), name="normal", include_submodules=True)
    normal.set_base_path(tmp_path)
    await normal.pull_code()
    cached = storage(tmp_path, repo, "cached", include_submodules=True)
    await cached.pull_code()
    shutil.rmtree(tmp_path / "cache")
    assert_same_checkout(normal.destination, cached.destination)
    assert_same_checkout(
        normal.destination / "modules/child", cached.destination / "modules/child"
    )
    git(cached.destination / "modules/child", "fsck", "--full")


async def test_warm_cache_reuses_objects(
    tmp_path: Path, source: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
):
    repo, _ = source
    trace = tmp_path / "trace.jsonl"
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(trace))
    await storage(tmp_path, repo, "cold").pull_code()
    trace.unlink()
    await storage(tmp_path, repo, "warm").pull_code()
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    server_pack_sessions = {
        event["sid"]
        for event in events
        if event.get("event") == "cmd_name"
        and event.get("hierarchy", "").endswith("upload-pack/pack-objects")
    }
    packed = [
        int(event["value"])
        for event in events
        if event.get("key") == "write_pack_file/wrote"
        and event["sid"] in server_pack_sessions
    ]
    assert packed and sum(packed) == 0, packed


async def test_credentials_are_not_persisted_in_mirror(
    tmp_path: Path, source: tuple[Path, str]
):
    repo, commit = source
    git(repo, "update-server-info")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(SimpleHTTPRequestHandler, directory=str(repo / ".git")),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://user:cache-test-secret@127.0.0.1:{server.server_port}/"
        for name in ("cold", "warm"):
            run = GitRepository(
                url=url, commit_sha=commit, name=name, cache_dir=tmp_path / "cache"
            )
            run.set_base_path(tmp_path)
            await run.pull_code()
        configs = list((tmp_path / "cache").rglob("config"))
        assert len(configs) == 1
        assert "cache-test-secret" not in configs[0].read_text()
        assert not list((tmp_path / "cache").rglob("FETCH_HEAD"))
        assert git(run.destination, "remote", "get-url", "origin") == url
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


async def test_repository_count_eviction(tmp_path: Path, source: tuple[Path, str]):
    repo, _ = source
    first = storage(tmp_path, repo, "first")
    await first.pull_code()
    cache = tmp_path / "cache/prefect-git-v1"
    oldest = next(cache.iterdir())
    for i in range(8):
        other = tmp_path / f"remote-{i}"
        shutil.copytree(repo, other)
        await storage(tmp_path, other, f"run-{i}").pull_code()
    assert len(list(cache.iterdir())) == 8
    assert not oldest.exists()
    git(first.destination, "fsck", "--full")


def test_cache_path_roundtrip_preserves_runtime_home():
    repo = GitRepository(
        url="https://example.invalid/repo.git", cache_dir="~/.cache/prefect"
    )
    assert (
        repo.to_pull_step()["prefect.deployments.steps.git_clone"]["cache_dir"]
        == "~/.cache/prefect"
    )


async def test_failed_cold_fetch_leaves_no_published_entry(tmp_path: Path):
    run = storage(tmp_path, tmp_path / "missing-remote", "run")
    with pytest.raises(RuntimeError, match="Git object cache"):
        await run.pull_code()
    assert not run.destination.exists()
    assert not list((tmp_path / "cache/prefect-git-v1").iterdir())


async def test_cache_excludes_unrequested_history(
    tmp_path: Path, source: tuple[Path, str]
):
    repo, _ = source
    git(repo, "checkout", "--orphan", "unrelated")
    git(repo, "rm", "-rf", ".")
    (repo / "unrelated.txt").write_text("unrelated branch payload")
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "unrelated history")
    unrelated = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "unrelated-tag")
    git(repo, "update-ref", "refs/pull/123/head", unrelated)
    git(repo, "checkout", "main")
    for name in ("cold", "warm"):
        await storage(tmp_path, repo, name, branch="main").pull_code()
        entry = next((tmp_path / "cache/prefect-git-v1").iterdir())
        with pytest.raises(subprocess.CalledProcessError):
            git(entry, "cat-file", "-e", unrelated)


async def test_oversized_cache_bypasses_repeated_population(
    tmp_path: Path, source: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
):
    repo, _ = source
    monkeypatch.setattr("prefect.runner.storage._GIT_CACHE_MAX_BYTES", 1)
    await storage(tmp_path, repo, "cold").pull_code()
    cache = tmp_path / "cache/prefect-git-v1"
    entry = next(cache.iterdir())
    assert [p.name for p in entry.iterdir()] == ["bypass"]
    trace = tmp_path / "trace.jsonl"
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(trace))
    for name in ("second", "third"):
        run = storage(tmp_path, repo, name)
        await run.pull_code()
        git(run.destination, "fsck", "--full")
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    commands = [
        event.get("name") for event in events if event.get("event") == "cmd_name"
    ]
    assert commands.count("clone") == 2
    assert "init" not in commands
    assert "fetch" not in commands
    assert [p.name for p in entry.iterdir()] == ["bypass"]


async def test_busy_repository_does_not_block_other_repositories_or_get_pruned(
    tmp_path: Path, source: tuple[Path, str]
):
    repo, _ = source
    await storage(tmp_path, repo, "first").pull_code()
    cache = tmp_path / "cache/prefect-git-v1"
    entry = next(cache.iterdir())
    other = tmp_path / "other-remote"
    shutil.copytree(repo, other)
    with FileLock(cache / f"{entry.name}.lock"):
        await asyncio.wait_for(
            storage(tmp_path, other, "second").pull_code(), timeout=20
        )
        GitRepository._prune_git_cache(cache, max_entries=0)
        assert entry.exists()
    GitRepository._prune_git_cache(cache, max_entries=0)
    assert not list(cache.iterdir())
    git(tmp_path / "first", "fsck", "--full")
    git(tmp_path / "second", "fsck", "--full")


@pytest.mark.parametrize("selection", ["main", "v1"])
async def test_rewritten_refs_match_normal_clone(
    tmp_path: Path, source: tuple[Path, str], selection: str
):
    repo, old = source
    await storage(tmp_path, repo, "first", branch=selection).pull_code()
    if selection == "main":
        git(repo, "reset", "--hard", old)
    else:
        git(repo, "tag", "--force", "-a", "v1", "-m", "replacement")
    normal = GitRepository(url=repo.as_uri(), name="normal", branch=selection)
    normal.set_base_path(tmp_path)
    await normal.pull_code()
    cached = storage(tmp_path, repo, "second", branch=selection)
    await cached.pull_code()
    assert_same_checkout(normal.destination, cached.destination)
    assert git(normal.destination, "tag", "--list") == git(
        cached.destination, "tag", "--list"
    )
