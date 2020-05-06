from unittest.mock import MagicMock

import pytest
import requests

import prefect
from prefect.tasks.github import CreateBranch, GetRepoInfo
from prefect.utilities.configuration import set_temporary_config


class TestGetRepoInfoInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = GetRepoInfo()
        assert task.repo is None
        assert task.info_keys == []

    def test_additional_kwargs_passed_upstream(self):
        task = GetRepoInfo(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["repo", "info_keys"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = GetRepoInfo(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_repo_is_required_eventually(self):
        task = GetRepoInfo()
        with pytest.raises(ValueError, match="repo"):
            task.run()


class TestCreateBranchInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = CreateBranch()
        assert task.repo is None
        assert task.base == "master"
        assert task.branch_name is None

    def test_additional_kwargs_passed_upstream(self):
        task = CreateBranch(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["repo", "base", "branch_name"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = CreateBranch(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_repo_is_required_eventually(self):
        task = CreateBranch(branch_name="bob")
        with pytest.raises(ValueError, match="repo"):
            task.run()

    def test_branch_name_is_required_eventually(self):
        task = CreateBranch(repo="org/bob")
        with pytest.raises(ValueError, match="branch name"):
            task.run()


# deprecated
def test_base_name_is_filtered_for(monkeypatch):
    task = CreateBranch(base="BOB", branch_name="NEWBRANCH")

    payload = [{"ref": "refs/heads/BOB", "object": {"sha": "salty"}}]

    get = MagicMock(return_value=MagicMock(json=MagicMock(return_value=payload)))
    post = MagicMock()

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)

    task.run(repo="org/repo", token={"key": 42})

    assert post.call_args[1]["json"] == {
        "ref": "refs/heads/NEWBRANCH",
        "sha": "salty",
    }
