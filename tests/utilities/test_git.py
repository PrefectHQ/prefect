from unittest.mock import MagicMock

import pytest

dulwich = pytest.importorskip("dulwich")

from prefect.utilities.git import TemporaryGitRepo


@pytest.fixture
def fake_dulwich_porcelain_clone(monkeypatch):
    fake_clone = MagicMock()
    monkeypatch.setattr("dulwich.porcelain.clone", fake_clone)
    return fake_clone


@pytest.fixture
def fake_dulwich_build_index_from_tree(monkeypatch):
    fake_build_index_from_tree = MagicMock()
    monkeypatch.setattr(
        "dulwich.index.build_index_from_tree", fake_build_index_from_tree
    )
    return fake_build_index_from_tree


def test_temp_git_repo_init():
    repo = TemporaryGitRepo(
        git_clone_url="https://github.com/my/repo",
        branch_name="my-branch",
        tag=None,
        commit=None,
        clone_depth=2,
    )

    assert repo.git_clone_url == "https://github.com/my/repo"
    assert repo.branch_name == "my-branch"
    assert repo.tag == None
    assert repo.clone_depth == 2
    assert repo.commit == None


def test_temp_git_repo_raises_if_both_tag_and_branch_provided():
    with pytest.raises(ValueError):
        repo = TemporaryGitRepo(
            git_clone_url="https://github.com/my/repo",
            branch_name="my-branch",
            tag="v0.1",
            clone_depth=2,
        )


def test_temp_git_repo_context_management(
    fake_dulwich_porcelain_clone, fake_dulwich_build_index_from_tree
):
    with TemporaryGitRepo(
        git_clone_url="git@github.com/test/repo",
        branch_name=None,
        tag=None,
        clone_depth=1,
    ) as temp_repo:
        fake_dulwich_porcelain_clone.assert_called_with(
            depth=temp_repo.clone_depth,
            source=temp_repo.git_clone_url,
            target=temp_repo.temp_dir.name,
        )
        fake_dulwich_build_index_from_tree.assert_not_called()


@pytest.mark.parametrize("branch_name, tag", [("my-branch", None), (None, "v0.1")])
def test_temp_git_repo_context_management_with_branch_or_tag_checks_out_ref(
    branch_name, tag, fake_dulwich_porcelain_clone, fake_dulwich_build_index_from_tree
):
    with TemporaryGitRepo(
        git_clone_url="git@github.com/test/repo",
        branch_name=branch_name,
        tag=tag,
        clone_depth=1,
    ) as temp_repo:
        fake_dulwich_porcelain_clone.assert_called_with(
            depth=temp_repo.clone_depth,
            source=temp_repo.git_clone_url,
            target=temp_repo.temp_dir.name,
        )
        fake_dulwich_build_index_from_tree.assert_called()


@pytest.mark.parametrize(
    "branch_name, tag, expected_ref",
    [
        ("my-branch", None, b"refs/remotes/origin/my-branch"),
        (None, "v0.1", b"refs/tags/v0.1"),
    ],
)
def test_temp_git_repo_ref_for_branch_or_tag(branch_name, tag, expected_ref):
    temp_repo = TemporaryGitRepo(
        git_clone_url="git@github.com/test/repo",
        branch_name=branch_name,
        tag=tag,
        clone_depth=1,
    )
    assert temp_repo.branch_or_tag_ref == expected_ref
