import os
from prefect_azuredevops.credentials import AzureDevOpsCredentials

def test_auth_header_encoding():
    creds = AzureDevOpsCredentials(token="abc123", username="me")
    hdr = creds.get_auth_header()["Authorization"]
    assert hdr.startswith("Basic ")
    # decode and ensure token present
    import base64
    payload = base64.b64decode(hdr.split()[1]).decode()
    assert payload == "me:abc123"

def test_git_askpass_script(tmp_path):
    creds = AzureDevOpsCredentials(token="secret", username="u")
    with creds.git_askpass_env() as env:
        assert "GIT_ASKPASS" in env
        path = env["GIT_ASKPASS"]
        assert os.path.exists(path)
        assert os.access(path, os.X_OK)
    # script removed after context
    assert not os.path.exists(path)
