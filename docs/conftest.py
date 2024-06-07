import warnings

import pytest


@pytest.fixture
def my_k8s_job():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        from prefect_kubernetes import KubernetesJob

        KubernetesJob(v1_job={}, credentials={}).save("my-k8s-job", overwrite=True)


@pytest.fixture(autouse=True)
def filter_all_warnings():
    warnings.filterwarnings("ignore")
    yield
    warnings.resetwarnings()


@pytest.fixture
def demo_repo():
    from prefect_github import GitHubRepository

    GitHubRepository(repository_url="https://github.com/PrefectHQ/prefect").save(
        "demo-repo", overwrite=True
    )
