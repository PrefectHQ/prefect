import os
from typing import Union
from unittest import mock

import pytest

from prefect.server.database.orm_models import Mapped, Run, mapped_column, sa

SKIP_FILES = {
    "docs/3.0/deploy/index.mdx": "Needs database fixtures",
    "docs/3.0/deploy/run-flows-in-local-processes.mdx": "Needs blocks setup",
    "docs/3.0/develop/blocks.mdx": "Block subclasses defined in docs cannot be properly registered due to test environment limitations",
    "docs/3.0/develop/manage-states.mdx": "Needs some extra import help",
    "docs/3.0/develop/results.mdx": "Needs block cleanup handling",
    "docs/3.0/develop/task-caching.mdx": "Tasks defined in docs cannot be properly inspected due to test environment limitations",
    "docs/3.0/develop/task-run-limits.mdx": "Await outside of async function",
    "docs/3.0/develop/task-runners.mdx": "Tasks defined in docs cannot be properly inspected due to test environment limitations",
    "docs/3.0/develop/write-tasks.mdx": "Tasks defined in docs cannot be properly inspected due to test environment limitations",
    "docs/3.0/manage/interact-with-api.mdx": "Async function outside of async context",
    "docs/3.0/resources/big-data.mdx": "Needs block cleanup handling",
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
    "docs/3.0/resources/upgrade-agents-to-workers.mdx": "Needs Debugging",
    "docs/3.0/resources/upgrade-to-prefect-3.mdx": "Needs Debugging",
    "docs/contribute/develop-a-new-worker-type.mdx": "Needs Debugging",
    "docs/integrations/prefect-aws/index.mdx": "Needs Debugging",
    "docs/integrations/prefect-shell/index.mdx": "Needs Debugging",
    # --- Below this line are files that pass locally but fail in CI ---
    "docs/3.0/api-ref/rest-api/index.mdx": "Needs Debugging in CI",
    "docs/3.0/automate/add-schedules.mdx": "Needs Debugging in CI",
    "docs/3.0/develop/deferred-tasks.mdx": "Needs Debugging in CI",
    "docs/3.0/develop/logging.mdx": "Needs Debugging in CI",
    "docs/3.0/develop/variables.mdx": "Needs Debugging in CI",
    "docs/3.0/develop/write-flows.mdx": "Needs Debugging in CI",
}


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def pytest_collection_modifyitems(items):
    for item in items:
        for file, reason in SKIP_FILES.items():
            full_path = os.path.join(project_root, file)
            if str(item.fspath) == full_path:
                item.add_marker(pytest.mark.skip(reason=reason))


@pytest.fixture(autouse=True)
def mock_runner_start():
    with mock.patch("prefect.cli.flow.Runner.start", new_callable=mock.AsyncMock):
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
