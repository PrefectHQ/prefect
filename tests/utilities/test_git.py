import pytest

from prefect.utilities.git import TemporaryGitRepo


def test_temp_git_repo_init():
    repo = TemporaryGitRepo(
        git_clone_url="https://github.com/my/repo",
        branch_name="my-branch",
        tag=None,
        clone_depth=2,
    )

    assert repo.git_clone_url == "https://github.com/my/repo"
    assert repo.branch_name == "my-branch"
    assert repo.tag == None
    assert repo.clone_depth == 2


def test_temp_git_repo_raises_if_both_tag_and_branch_provided():
    with pytest.raises(ValueError):
        repo = TemporaryGitRepo(
            git_clone_url="https://github.com/my/repo",
            branch_name="my-branch",
            tag="v0.1",
            clone_depth=2,
        )


# TODO - finish up tests here
