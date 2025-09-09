from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from prefect.server.concurrency.lease_storage import ConcurrencyLimitLeaseMetadata
from prefect.server.utilities.leasing import ResourceLease


def test_serialize_deserialize_preserves_holder():
    from prefect_redis.lease_storage import ConcurrencyLeaseStorage

    storage = ConcurrencyLeaseStorage(redis_client=None)  # client not needed here

    # Prepare a lease with metadata and a holder dict
    holder = {"type": "task_run", "id": str(uuid4())}
    lease = ResourceLease(
        resource_ids=[uuid4()],
        expiration=datetime.now(timezone.utc) + timedelta(seconds=60),
        metadata=ConcurrencyLimitLeaseMetadata(slots=2),
    )
    # Set via setattr to mirror production behavior and ensure serialization works
    setattr(lease.metadata, "holder", holder)

    payload = storage._serialize_lease(lease)
    roundtrip = storage._deserialize_lease(payload)

    assert roundtrip.metadata is not None
    assert roundtrip.metadata.slots == 2
    # Holder should survive round-trip
    assert getattr(roundtrip.metadata, "holder", None) == holder


def test_deserialize_sets_holder_via_setattr_for_backward_compatibility(monkeypatch):
    from prefect_redis import lease_storage as ls_mod

    # Define a legacy metadata type without a 'holder' field
    class LegacyMeta:
        def __init__(self, slots: int):
            self.slots = slots

    # Monkeypatch the metadata class used by the module
    monkeypatch.setattr(ls_mod, "ConcurrencyLimitLeaseMetadata", LegacyMeta)

    storage = ls_mod.ConcurrencyLeaseStorage(redis_client=None)

    holder = {"type": "flow_run", "id": str(uuid4())}
    data = {
        "id": str(uuid4()),
        "resource_ids": [str(uuid4())],
        "expiration": "2025-01-01T00:00:00+00:00",
        "created_at": "2025-01-01T00:00:00+00:00",
        "metadata": {"slots": 1, "holder": holder},
    }

    lease = storage._deserialize_lease(json.dumps(data))

    assert isinstance(lease.metadata, LegacyMeta)
    assert lease.metadata.slots == 1
    # setattr path should attach 'holder' even if the class didn't define it
    assert getattr(lease.metadata, "holder", None) == holder
