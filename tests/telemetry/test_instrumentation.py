from uuid import UUID

import pytest

from prefect.telemetry.instrumentation import extract_account_and_workspace_id

ACCOUNT_ID = UUID("11111111-1111-1111-1111-111111111111")
WORKSPACE_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_extract_account_and_workspace_id_valid_url():
    url = (
        f"https://api.prefect.cloud/api/accounts/{ACCOUNT_ID}/"
        f"workspaces/{WORKSPACE_ID}"
    )
    account_id, workspace_id = extract_account_and_workspace_id(url)
    assert account_id == ACCOUNT_ID
    assert workspace_id == WORKSPACE_ID


@pytest.mark.parametrize(
    "url",
    [
        "https://api.prefect.cloud/api/invalid",
        f"https://api.prefect.cloud/api/accounts/invalid-uuid/workspaces/{WORKSPACE_ID}",
        "https://api.prefect.cloud/api/accounts/{ACCOUNT_ID}/invalid",
        "https://api.prefect.cloud/api/workspaces/{WORKSPACE_ID}",
    ],
)
def test_extract_account_and_workspace_id_invalid_urls(url):
    with pytest.raises(
        ValueError, match="Could not extract account and workspace id from url"
    ):
        extract_account_and_workspace_id(url)
