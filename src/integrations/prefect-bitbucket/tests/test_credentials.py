import pytest
from atlassian.bitbucket import Bitbucket, Cloud
from prefect_bitbucket.credentials import BitBucketCredentials, ClientType

from prefect.blocks.core import Block


@pytest.mark.parametrize("token", [None, "token_value"])
def test_bitbucket_credentials(token):
    """Test credentials is Block type."""
    credentials_block = BitBucketCredentials(token=token)
    assert isinstance(credentials_block, Block)


def ensure_valid_bitbucket_username_passes():
    """Ensure invalid char username raises."""
    try:
        BitBucketCredentials(token="token", username="validusername")
    except Exception as exc:
        assert False, f"Valid username raised an exception {exc}"


def test_bitbucket_username_invalid_char():
    """Ensure invalid char username raises."""
    with pytest.raises(ValueError):
        BitBucketCredentials(token="token", username="invalid!username")


def test_bitbucket_username_at_max_length_passes():
    """Ensure a username of exactly 100 characters is allowed."""
    username = "a" * 100
    creds = BitBucketCredentials(token="token", username=username)
    assert creds.username == username


@pytest.mark.parametrize(
    "client_type",
    ["local", "LOCAL", "cloud", "Cloud", ClientType.LOCAL, ClientType.CLOUD],
)
def test_bitbucket_get_client(client_type):
    bitbucket_credentials = BitBucketCredentials(
        url="my-url", username="my-username", password="my-password"
    )
    client = bitbucket_credentials.get_client(client_type=client_type)
    if not isinstance(client_type, str):
        client_type = client_type.value

    if client_type.lower() == "local":
        assert isinstance(client, Bitbucket)
    else:
        assert isinstance(client, Cloud)


def test_bitbucket_username_with_email_passes():
    """Ensure email-style usernames are accepted."""
    creds = BitBucketCredentials(
        token="dummy-token", username="devops.team+ci@scalefocus.com"
    )
    assert creds.username == "devops.team+ci@scalefocus.com"


def test_format_git_credentials_cloud():
    """Test that BitBucket Cloud credentials get x-token-auth: prefix and are embedded in URL."""
    credentials = BitBucketCredentials(token="my-token")
    result = credentials.format_git_credentials("https://bitbucket.org/org/repo.git")
    assert result == "https://x-token-auth:my-token@bitbucket.org/org/repo.git"


def test_format_git_credentials_cloud_already_prefixed():
    """Test that already-prefixed tokens are used as-is in URL."""
    credentials = BitBucketCredentials(token="x-token-auth:my-token")
    result = credentials.format_git_credentials("https://bitbucket.org/org/repo.git")
    assert result == "https://x-token-auth:my-token@bitbucket.org/org/repo.git"


def test_format_git_credentials_server():
    """Test that BitBucket Server credentials use username:token format in URL."""
    credentials = BitBucketCredentials(token="my-token", username="myuser")
    result = credentials.format_git_credentials(
        "https://bitbucketserver.com/scm/project/repo.git"
    )
    assert result == "https://myuser:my-token@bitbucketserver.com/scm/project/repo.git"


def test_format_git_credentials_server_no_username_raises():
    """Test that BitBucket Server without username raises ValueError."""
    credentials = BitBucketCredentials(token="my-token")
    with pytest.raises(
        ValueError, match="Username is required for BitBucket Server authentication"
    ):
        credentials.format_git_credentials(
            "https://bitbucketserver.com/scm/project/repo.git"
        )


def test_format_git_credentials_no_token_raises():
    """Test that missing token raises ValueError."""
    credentials = BitBucketCredentials()
    with pytest.raises(
        ValueError, match="Token or password is required for BitBucket authentication"
    ):
        credentials.format_git_credentials("https://bitbucket.org/org/repo.git")


def test_format_git_credentials_escapes_forward_slash():
    """Regression test for issue #19419: tokens with forward slashes must be URL-encoded.

    Bitbucket access tokens can contain forward slashes (base64 encoding uses them).
    These must be encoded as %2F to avoid being interpreted as path separators.
    """
    credentials = BitBucketCredentials(token="abc123/def456/ghi789")
    result = credentials.format_git_credentials("https://bitbucket.org/org/repo.git")
    # forward slashes should be encoded as %2F
    assert (
        result
        == "https://x-token-auth:abc123%2Fdef456%2Fghi789@bitbucket.org/org/repo.git"
    )
    # ensure raw slashes don't appear in the credentials portion
    credentials_part = result.split("@")[0].split("//")[1]
    assert "/" not in credentials_part, (
        "credentials should not contain unencoded slashes"
    )


def test_format_git_credentials_escapes_base64_characters():
    """Ensure base64 characters (+, /, =) in tokens are properly escaped.

    Base64-encoded tokens use A-Z, a-z, 0-9, +, /, and = characters.
    All special characters must be URL-encoded for use in credentials.
    """
    credentials = BitBucketCredentials(token="aBc+DeF/gHi=")
    result = credentials.format_git_credentials("https://bitbucket.org/org/repo.git")
    # + should be %2B, / should be %2F, = should be %3D
    assert (
        result == "https://x-token-auth:aBc%2BDeF%2FgHi%3D@bitbucket.org/org/repo.git"
    )


def test_format_git_credentials_server_escapes_special_characters():
    """Ensure special characters in server credentials are URL-encoded."""
    credentials = BitBucketCredentials(
        token="token/with/slashes", username="user@domain.com"
    )
    result = credentials.format_git_credentials(
        "https://bitbucketserver.com/scm/project/repo.git"
    )
    # both username and token should have special characters encoded
    assert (
        result
        == "https://user%40domain.com:token%2Fwith%2Fslashes@bitbucketserver.com/scm/project/repo.git"
    )


def test_format_git_credentials_self_hosted_instance():
    """Regression test for issue #19512: self-hosted instances without 'bitbucketserver' in hostname.

    Self-hosted BitBucket Server instances may not have 'bitbucketserver' in their hostname
    (e.g., git.example.com), but still require username:password authentication.
    When username is provided, it should use username:password format regardless of hostname.
    """
    credentials = BitBucketCredentials(token="my-token", username="myuser")
    result = credentials.format_git_credentials(
        "https://git.example.com/scm/project/repo.git"
    )
    # Should use username:password format, not x-token-auth:
    assert result == "https://myuser:my-token@git.example.com/scm/project/repo.git"


def test_format_git_credentials_self_hosted_instance_with_special_chars():
    """Test self-hosted instances with special characters in credentials.

    Ensures that username:password auth works correctly for self-hosted instances
    even when credentials contain special characters that need URL encoding.
    """
    credentials = BitBucketCredentials(
        password="p@ss!word/123", username="user@domain.com"
    )
    result = credentials.format_git_credentials(
        "https://git.example.com/scm/project/repo.git"
    )
    # Both username and password should be URL-encoded
    assert (
        result
        == "https://user%40domain.com:p%40ss%21word%2F123@git.example.com/scm/project/repo.git"
    )
