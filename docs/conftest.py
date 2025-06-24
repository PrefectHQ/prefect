import glob
import os
from typing import Union
from unittest import mock

import pytest

from prefect.server.database.orm_models import Mapped, Run, mapped_column, sa

SKIP_FILES = {
    "docs/v3/concepts/deployments.mdx": "Needs database fixtures",
    "docs/v3/how-to-guides/deployment_infra/run-flows-in-local-processes.mdx": "Needs blocks setup",
    "docs/v3/develop/blocks.mdx": "Block subclasses defined in docs cannot be properly registered due to test environment limitations",
    "docs/v3/develop/manage-states.mdx": "Needs some extra import help",
    "docs/v3/concepts/results.mdx": "Needs block cleanup handling",
    "docs/v3/how-to-guides/workflows/cache-workflow-steps.mdx": "Tasks defined in docs cannot be properly inspected due to test environment limitations",
    "docs/v3/how-to-guides/workflows/tag-based-concurrency-limits.mdx": "Await outside of async function",
    "docs/v3/how-to-guides/workflows/global-concurrency-limits.mdx": "Await outside of async function",
    "docs/v3/concepts/task-runners.mdx": "Tasks defined in docs cannot be properly inspected due to test environment limitations",
    "docs/v3/how-to-guides/workflows/write-and-run.mdx": "Tasks defined in docs cannot be properly inspected due to test environment limitations",
    "docs/v3/develop/interact-with-api.mdx": "Async function outside of async context",
    "docs/v3/develop/big-data.mdx": "Needs block cleanup handling",
    "docs/contribute/dev-contribute.mdx": "SQLAlchemy model modifications can't be safely tested without affecting the global database schema",
    "docs/integrations/prefect-azure/index.mdx": "Makes live network calls which should be mocked",
    "docs/integrations/prefect-bitbucket/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-dask/index.mdx": "Needs a `dask_cloudprovider` harness",
    "docs/integrations/prefect-dask/usage_guide.mdx": "Attempts to start a dask cluster",
    "docs/integrations/prefect-databricks/index.mdx": "Pydantic failures",
    "docs/integrations/prefect-dbt/index.mdx": "Needs block cleanup handling, and prefect-dbt installed",
    "docs/integrations/prefect-email/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-gcp/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-github/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-gitlab/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-kubernetes/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-slack/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-snowflake/index.mdx": "Needs block cleanup handling",
    "docs/integrations/prefect-sqlalchemy/index.mdx": "Needs block cleanup handling",
    "docs/integrations/use-integrations.mdx": "Pydantic failures",
    # --- Below this line are files that haven't been debugged yet. ---
    "docs/v3/how-to-guides/migrate/upgrade-agents-to-workers.mdx": "Needs Debugging",
    "docs/v3/how-to-guides/migrate/upgrade-to-prefect-3.mdx": "Needs Debugging",
    "docs/contribute/develop-a-new-worker-type.mdx": "Needs Debugging",
    "docs/integrations/prefect-aws/index.mdx": "Needs Debugging",
    "docs/integrations/prefect-shell/index.mdx": "Needs Debugging",
    # --- Below this line are files that pass locally but fail in CI ---
    "docs/v3/api-ref/rest-api/index.mdx": "Needs Debugging in CI",
    "docs/v3/how-to-guides/deployments/create-schedules.mdx": "Needs Debugging in CI",
    "docs/v3/develop/logging.mdx": "Needs Debugging in CI",
    "docs/v3/develop/variables.mdx": "Needs Debugging in CI",
    "docs/v3/develop/write-flows.mdx": "Needs Debugging in CI",
    # --- Below this line are files that need a release of a new Prefect integration ---
    "docs/v3/advanced/submit-flows-directly-to-dynamic-infrastructure.mdx": "Needs a release of prefect-docker",
}


examples = {
    example: "Skipping examples that live in separate repository"
    for example in glob.glob("docs/v3/examples/*.mdx")
}
SKIP_FILES.update(examples)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def pytest_collection_modifyitems(items):
    for item in items:
        # Skip files in apiref/python directory
        if "api-ref/python/" in str(item.fspath):
            item.add_marker(
                pytest.mark.skip(reason="Skipping API reference Python files")
            )
            continue

        # Skip hardcoded files
        for file, reason in SKIP_FILES.items():
            full_path = os.path.join(project_root, file)
            if str(item.fspath) == full_path:
                item.add_marker(pytest.mark.skip(reason=reason))
                break


@pytest.fixture(autouse=True)
def mock_runner_start():
    with mock.patch("prefect.cli.flow.Runner.start", new_callable=mock.AsyncMock):
        yield


@pytest.fixture(autouse=True)
def mock_base_worker_submit():
    with (
        mock.patch(
            "prefect.workers.base.BaseWorker.submit", new_callable=mock.AsyncMock
        ),
        mock.patch(
            "prefect_kubernetes.worker.KubernetesWorker.submit",
            new_callable=mock.AsyncMock,
        ),
    ):
        yield


def pytest_markdown_docs_globals():
    return {
        "Mapped": Mapped,
        "Run": Run,
        "Union": Union,
        "mapped_column": mapped_column,
        "sa": sa,
    }


@pytest.fixture
def mock_post_200(monkeypatch):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = []

    def mock_post(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("requests.post", mock_post)
    return mock_response
