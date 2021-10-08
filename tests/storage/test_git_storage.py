from unittest.mock import MagicMock

import pytest

dulwich = pytest.importorskip("dulwich")

from prefect import context, Flow
from prefect.storage import Git


@pytest.fixture
def fake_temp_repo(monkeypatch):
    temp_repo = MagicMock()
    temp_repo.return_value.__enter__.return_value.temp_dir.name = "/tmp/test/"
    monkeypatch.setattr("prefect.storage.git.TemporaryGitRepo", temp_repo)
    return temp_repo


@pytest.fixture
def fake_extract_flow_from_file(monkeypatch):
    fake_extract_flow = MagicMock()
    monkeypatch.setattr("prefect.storage.git.extract_flow_from_file", fake_extract_flow)
    return fake_extract_flow


def test_create_git_storage():
    storage = Git(repo="test/repo", flow_path="flow.py")
    assert storage
    assert storage.logger


def test_create_git_storage_init_args():
    storage = Git(
        flow_path="flow.py",
        repo="test/repo",
        repo_host="bitbucket.org",
        flow_name="my-flow",
        git_token_secret_name="MY_TOKEN",
        git_token_username="my_user",
        branch_name="my_branch",
        tag=None,
        commit=None,
        clone_depth=1,
        use_ssh=False,
        format_access_token=True,
    )
    assert storage
    assert storage.flows == dict()
    assert storage.flow_path == "flow.py"
    assert storage.repo == "test/repo"
    assert storage.repo_host == "bitbucket.org"
    assert storage.flow_name == "my-flow"
    assert storage.git_token_secret_name == "MY_TOKEN"
    assert storage.git_token_username == "my_user"
    assert storage.branch_name == "my_branch"
    assert storage.tag is None
    assert storage.commit is None
    assert storage.clone_depth == 1
    assert storage.use_ssh == False
    assert storage.format_access_token == True


def test_create_git_storage_with_use_ssh_and_git_token_secret_name_logs_warning(caplog):
    storage = Git(
        flow_path="flow.py",
        repo="test/repo",
        git_token_secret_name="MY_SECRET",
        use_ssh=True,
    )

    assert (
        "Git Storage initialized with `use_ssh = True` and `git_token_secret_name` provided. SSH will be used to clone the repository. `git_token_secret_name` will be ignored"
        in caplog.text
    )


def test_create_git_storage_with_git_clone_url_secret_name_and_other_repo_params_logs_warning(
    caplog,
):
    storage = Git(
        flow_path="flow.py",
        repo="test/repo",
        git_clone_url_secret_name="MY_SECRET",
    )

    assert (
        "Git storage initialized with a `git_clone_url_secret_name`. The value of this Secret will be used to clone the repository, ignoring"
        in caplog.text
    )


def test_create_git_storage_without_repo_or_git_clone_url_secret_name_errors():
    with pytest.raises(
        ValueError,
        match="Either `repo` or `git_clone_url_secret_name` must be provided",
    ):
        storage = Git(flow_path="flow.py")


def test_create_git_storage_with_tag_and_branch_name_errors():
    with pytest.raises(ValueError):
        storage = Git(
            flow_path="flow.py", repo="test/repo", branch_name="my_branch", tag="v0.1"
        )


def test_serialize_git_storage():
    storage = Git(
        flow_path="flow.py",
        repo="test/repo",
        repo_host="bitbucket.org",
        flow_name="my-flow",
        git_token_secret_name="MY_TOKEN",
        git_token_username="my_user",
        git_clone_url_secret_name="MY_GIT_URL",
        branch_name="my_branch",
        tag=None,
        commit=None,
        clone_depth=1,
        use_ssh=False,
        format_access_token=True,
    )
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "Git"
    assert serialized_storage["repo"] == "test/repo"
    assert serialized_storage["flow_path"] == "flow.py"
    assert serialized_storage["repo_host"] == "bitbucket.org"
    assert serialized_storage["flow_name"] == "my-flow"
    assert serialized_storage["git_token_secret_name"] == "MY_TOKEN"
    assert serialized_storage["git_token_username"] == "my_user"
    assert serialized_storage["git_clone_url_secret_name"] == "MY_GIT_URL"
    assert serialized_storage["branch_name"] == "my_branch"
    assert serialized_storage["tag"] == None
    assert serialized_storage["commit"] == None
    assert serialized_storage["clone_depth"] == 1
    assert serialized_storage["use_ssh"] == False
    assert serialized_storage["format_access_token"] == True


def test_add_flow_to_git_storage():
    storage = Git(repo="test/repo", flow_path="flow.py")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage


def test_add_flow_to_git_already_added():
    storage = Git(repo="test/repo", flow_path="flow.py")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage

    with pytest.raises(ValueError):
        storage.add_flow(f)


@pytest.mark.parametrize(
    "repo_host, repo, access_token_secret_name, access_token_secret, access_token_username, use_ssh, format_access_token, git_clone_url_secret_name, git_clone_url_secret, expected_git_clone_url",
    [
        # no access token secret provided
        (
            "github.com",
            "my/repo",
            None,
            None,
            None,
            False,
            True,
            None,
            None,
            "https://@github.com/my/repo.git",
        ),
        # github + access token
        (
            "github.com",
            "user/repo",
            "MY_TOKEN",
            "MY_SECRET_TOKEN",
            None,
            False,
            True,
            None,
            None,
            "https://user:MY_SECRET_TOKEN@github.com/user/repo.git",
        ),
        # github + access token + custom token username
        (
            "github.com",
            "user/repo",
            "MY_TOKEN",
            "MY_SECRET_TOKEN",
            "another_git_user",
            False,
            True,
            None,
            None,
            "https://another_git_user:MY_SECRET_TOKEN@github.com/user/repo.git",
        ),
        # bitbucket + access token
        (
            "bitbucket.org",
            "user/repo",
            "MY_TOKEN",
            "MY_SECRET_TOKEN",
            None,
            False,
            True,
            None,
            None,
            "https://user:MY_SECRET_TOKEN@bitbucket.org/user/repo.git",
        ),
        # gitlab + access token
        (
            "gitlab.com",
            "user/repo",
            "MY_TOKEN",
            "MY_SECRET_TOKEN",
            None,
            False,
            True,
            None,
            None,
            "https://user:MY_SECRET_TOKEN@gitlab.com/user/repo.git",
        ),
        # unknown hostname + access token
        (
            "randomsite.com",
            "user/repo",
            "MY_TOKEN",
            "MY_SECRET_TOKEN",
            None,
            False,
            True,
            None,
            None,
            "https://user:MY_SECRET_TOKEN@randomsite.com/user/repo.git",
        ),
        # ssh
        (
            "github.com",
            "user/repo",
            "MY_TOKEN",
            "MY_SECRET_TOKEN",
            None,
            True,  # use ssh instead of https
            True,
            None,
            None,
            "git@github.com:user/repo.git",
        ),
        # skip access token formatting
        (
            "github.com",
            "user/repo",
            "MY_TOKEN",
            "MY_SECRET_TOKEN",
            None,
            False,
            False,  # skip access token formatting
            None,
            None,
            "https://MY_SECRET_TOKEN@github.com/user/repo.git",
        ),
        # provide git clone url secret name directly
        (
            None,
            None,
            None,
            None,
            None,
            False,
            True,
            "GIT_CLONE_URL_SECRET",  # provide the url as a secret
            "https://my-secret-url.com/repo.git",
            "https://my-secret-url.com/repo.git",
        ),
    ],
)
def test_get_git_clone_url(
    repo_host,
    repo,
    access_token_secret_name,
    access_token_secret,
    access_token_username,
    use_ssh,
    format_access_token,
    git_clone_url_secret_name,
    git_clone_url_secret,
    expected_git_clone_url,
):
    storage = Git(
        repo=repo,
        flow_path="foo.py",
        repo_host=repo_host,
        git_token_secret_name=access_token_secret_name,
        git_token_username=access_token_username,
        git_clone_url_secret_name=git_clone_url_secret_name,
        use_ssh=use_ssh,
        format_access_token=format_access_token,
    )
    with context(
        secrets={
            access_token_secret_name: access_token_secret,
            git_clone_url_secret_name: git_clone_url_secret,
        }
    ):
        assert storage.git_clone_url == expected_git_clone_url


def test_git_access_token_errors_if_provided_and_not_found(caplog):
    storage = Git(
        repo="test/repo", flow_path="flow.py", git_token_secret_name="MISSING"
    )
    with context(secrets={}):
        with pytest.raises(Exception, match="MISSING"):
            storage.git_token_secret


def test_get_flow(fake_temp_repo, fake_extract_flow_from_file):
    storage = Git(repo="test/repo", flow_path="flow.py", flow_name="my-flow")
    storage.add_flow(Flow("my-flow"))
    flow = storage.get_flow("my-flow")
    fake_temp_repo.assert_called_with(
        branch_name=storage.branch_name,
        clone_depth=storage.clone_depth,
        git_clone_url=storage.git_clone_url,
        tag=storage.tag,
        commit=storage.commit,
    )
    fake_extract_flow_from_file.assert_called_with(
        file_path=f"/tmp/test/{storage.flow_path}", flow_name=storage.flow_name
    )


def test_get_flow_file_not_found(fake_temp_repo, caplog):
    storage = Git(repo="test/repo", flow_path="flow.py", flow_name="my-flow")
    storage.add_flow(Flow("my-flow"))
    with pytest.raises(FileNotFoundError):
        flow = storage.get_flow("my-flow")

    fake_temp_repo.assert_called_with(
        branch_name=storage.branch_name,
        clone_depth=storage.clone_depth,
        git_clone_url=storage.git_clone_url,
        tag=storage.tag,
        commit=storage.commit,
    )
