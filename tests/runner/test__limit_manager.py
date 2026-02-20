from uuid import UUID

import anyio
import pytest

from prefect.runner._limit_manager import LimitManager


class TestLimitManagerNoLimit:
    """Tests for limit=None behavior (sentinel path)."""

    def test_no_limit_acquire_returns_uuid(self):
        lm = LimitManager(limit=None)
        result = lm.acquire()
        assert isinstance(result, UUID)

    def test_no_limit_release_is_noop(self):
        lm = LimitManager(limit=None)
        token = lm.acquire()
        lm.release(token)  # should not raise

    def test_no_limit_has_slots_available_returns_false(self):
        lm = LimitManager(limit=None)
        assert lm.has_slots_available() is False


class TestLimitManagerLifecycle:
    async def test_aenter_creates_limiter_when_limit_set(self):
        async with LimitManager(limit=3) as lm:
            assert isinstance(lm._limiter, anyio.CapacityLimiter)

    async def test_aenter_no_limiter_when_limit_none(self):
        async with LimitManager(limit=None) as lm:
            assert lm._limiter is None

    async def test_aexit_clears_limiter(self):
        lm = LimitManager(limit=2)
        async with lm:
            assert lm._limiter is not None
        assert lm._limiter is None


class TestLimitManagerAcquireRelease:
    async def test_acquire_returns_uuid_token(self):
        async with LimitManager(limit=2) as lm:
            token = lm.acquire()
            assert isinstance(token, UUID)

    async def test_acquire_borrows_from_limiter(self):
        async with LimitManager(limit=2) as lm:
            lm.acquire()
            assert lm._limiter.borrowed_tokens == 1

    async def test_release_frees_slot(self):
        async with LimitManager(limit=2) as lm:
            token = lm.acquire()
            lm.release(token)
            assert lm._limiter.borrowed_tokens == 0

    async def test_multiple_tokens_are_distinct(self):
        async with LimitManager(limit=3) as lm:
            token1 = lm.acquire()
            token2 = lm.acquire()
            assert token1 != token2
            assert lm._limiter.borrowed_tokens == 2


class TestLimitManagerCapacityExhaustion:
    async def test_acquire_raises_would_block_at_capacity(self):
        async with LimitManager(limit=1) as lm:
            lm.acquire()  # fills the one slot
            with pytest.raises(anyio.WouldBlock):
                lm.acquire()


class TestLimitManagerHasSlotsAvailable:
    async def test_has_slots_available_true_when_capacity_exists(self):
        async with LimitManager(limit=2) as lm:
            assert lm.has_slots_available() is True

    async def test_has_slots_available_false_when_at_capacity(self):
        async with LimitManager(limit=1) as lm:
            lm.acquire()
            assert lm.has_slots_available() is False

    async def test_has_slots_available_true_after_release(self):
        async with LimitManager(limit=1) as lm:
            token = lm.acquire()
            lm.release(token)
            assert lm.has_slots_available() is True
