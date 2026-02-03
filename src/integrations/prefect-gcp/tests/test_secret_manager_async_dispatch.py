"""Tests for async_dispatch migration in prefect-gcp secret_manager.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

from typing import Coroutine

import pytest
from prefect_gcp.secret_manager import (
    GcpSecret,
    acreate_secret,
    adelete_secret,
    adelete_secret_version,
    aread_secret,
    aupdate_secret,
    create_secret,
    delete_secret,
    delete_secret_version,
    read_secret,
    update_secret,
)

from prefect import flow


class TestCreateSecretAsyncDispatch:
    """Tests for create_secret migrated from @sync_compatible to @async_dispatch."""

    def test_create_secret_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """create_secret must return str (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            result = create_secret("test_secret", gcp_credentials)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, str)
        assert "test_secret" in result

    async def test_create_secret_async_context_works(self, gcp_credentials):
        """create_secret should work correctly in async context."""

        @flow
        async def test_flow():
            result = await acreate_secret("test_secret", gcp_credentials)
            return result

        result = await test_flow()
        assert isinstance(result, str)
        assert "test_secret" in result

    def test_acreate_secret_is_available(self):
        """acreate_secret should be available for direct async usage."""
        assert callable(acreate_secret)


class TestUpdateSecretAsyncDispatch:
    """Tests for update_secret migrated from @sync_compatible to @async_dispatch."""

    def test_update_secret_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """update_secret must return str (not coroutine) in sync context."""

        @flow
        def test_flow():
            create_secret("test_secret", gcp_credentials)
            result = update_secret("test_secret", "secret_value", gcp_credentials)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, str)

    async def test_update_secret_async_context_works(self, gcp_credentials):
        """update_secret should work correctly in async context."""

        @flow
        async def test_flow():
            await acreate_secret("test_secret", gcp_credentials)
            result = await aupdate_secret(
                "test_secret", "secret_value", gcp_credentials
            )
            return result

        result = await test_flow()
        assert isinstance(result, str)

    def test_aupdate_secret_is_available(self):
        """aupdate_secret should be available for direct async usage."""
        assert callable(aupdate_secret)


class TestReadSecretAsyncDispatch:
    """Tests for read_secret migrated from @sync_compatible to @async_dispatch."""

    def test_read_secret_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """read_secret must return str (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = read_secret("test_secret", gcp_credentials)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, str)

    async def test_read_secret_async_context_works(self, gcp_credentials):
        """read_secret should work correctly in async context."""

        @flow
        async def test_flow():
            result = await aread_secret("test_secret", gcp_credentials)
            return result

        result = await test_flow()
        assert isinstance(result, str)

    def test_aread_secret_is_available(self):
        """aread_secret should be available for direct async usage."""
        assert callable(aread_secret)


class TestDeleteSecretAsyncDispatch:
    """Tests for delete_secret migrated from @sync_compatible to @async_dispatch."""

    def test_delete_secret_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """delete_secret must return str (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = delete_secret("test_secret", gcp_credentials)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, str)

    async def test_delete_secret_async_context_works(self, gcp_credentials):
        """delete_secret should work correctly in async context."""

        @flow
        async def test_flow():
            result = await adelete_secret("test_secret", gcp_credentials)
            return result

        result = await test_flow()
        assert isinstance(result, str)

    def test_adelete_secret_is_available(self):
        """adelete_secret should be available for direct async usage."""
        assert callable(adelete_secret)


class TestDeleteSecretVersionAsyncDispatch:
    """Tests for delete_secret_version migrated from @sync_compatible to @async_dispatch."""

    def test_delete_secret_version_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """delete_secret_version must return str (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = delete_secret_version("test_secret", 1, gcp_credentials)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, str)

    async def test_delete_secret_version_async_context_works(self, gcp_credentials):
        """delete_secret_version should work correctly in async context."""

        @flow
        async def test_flow():
            result = await adelete_secret_version("test_secret", 1, gcp_credentials)
            return result

        result = await test_flow()
        assert isinstance(result, str)

    def test_adelete_secret_version_is_available(self):
        """adelete_secret_version should be available for direct async usage."""
        assert callable(adelete_secret_version)


class TestGcpSecretReadSecretAsyncDispatch:
    """Tests for GcpSecret.read_secret migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcp_secret(self, gcp_credentials):
        return GcpSecret(
            gcp_credentials=gcp_credentials, secret_name="test_secret_name"
        )

    def test_read_secret_sync_context_returns_value_not_coroutine(self, gcp_secret):
        """read_secret must return bytes (not coroutine) in sync context."""
        result = gcp_secret.read_secret()
        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, bytes)

    async def test_read_secret_async_context_works(self, gcp_secret):
        """read_secret should work correctly in async context."""
        result = await gcp_secret.aread_secret()
        assert isinstance(result, bytes)

    def test_aread_secret_is_available(self, gcp_secret):
        """aread_secret should be available for direct async usage."""
        assert hasattr(gcp_secret, "aread_secret")
        assert callable(gcp_secret.aread_secret)


class TestGcpSecretWriteSecretAsyncDispatch:
    """Tests for GcpSecret.write_secret migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcp_secret(self, gcp_credentials):
        return GcpSecret(
            gcp_credentials=gcp_credentials, secret_name="test_secret_name"
        )

    def test_write_secret_sync_context_returns_value_not_coroutine(self, gcp_secret):
        """write_secret must return str (not coroutine) in sync context."""
        result = gcp_secret.write_secret(b"test_data")
        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, str)

    async def test_write_secret_async_context_works(self, gcp_secret):
        """write_secret should work correctly in async context."""
        result = await gcp_secret.awrite_secret(b"test_data")
        assert isinstance(result, str)

    def test_awrite_secret_is_available(self, gcp_secret):
        """awrite_secret should be available for direct async usage."""
        assert hasattr(gcp_secret, "awrite_secret")
        assert callable(gcp_secret.awrite_secret)


class TestGcpSecretDeleteSecretAsyncDispatch:
    """Tests for GcpSecret.delete_secret migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcp_secret(self, gcp_credentials):
        return GcpSecret(
            gcp_credentials=gcp_credentials, secret_name="test_secret_name"
        )

    def test_delete_secret_sync_context_returns_value_not_coroutine(self, gcp_secret):
        """delete_secret must return str (not coroutine) in sync context."""
        result = gcp_secret.delete_secret()
        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, str)

    async def test_delete_secret_async_context_works(self, gcp_secret):
        """delete_secret should work correctly in async context."""
        result = await gcp_secret.adelete_secret()
        assert isinstance(result, str)

    def test_adelete_secret_is_available(self, gcp_secret):
        """adelete_secret should be available for direct async usage."""
        assert hasattr(gcp_secret, "adelete_secret")
        assert callable(gcp_secret.adelete_secret)
