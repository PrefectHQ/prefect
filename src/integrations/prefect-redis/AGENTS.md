# prefect-redis

Redis-backed implementations of Prefect server subsystems: event ordering, messaging, distributed locking/leases, and the worker cleanup queue.

## Purpose & Scope

Provides `CausalOrdering`, `Publisher`/`Consumer`, lease storage, and cleanup queue implementations that back `prefect.server.events`/`prefect.server.utilities.messaging` when Redis is the configured backend. Does not define the abstract interfaces it implements — those live in `prefect.server`.

## Redis Cluster hash-slot safety

Redis Cluster requires all keys touched by a single pipeline/transaction to hash to the same slot. `client.py` provides `cluster_key_prefix()`/`redis_key()`, which hash-tag a key (`{prefix}:suffix`) only when the configured URL uses the `redis+cluster://`/`rediss+cluster://` scheme — otherwise they're a no-op.

Any module that runs multi-key pipelines against Redis must build its keys through these helpers (see `ordering.py`'s `CausalOrdering._key`) rather than plain string interpolation, or the pipeline will fail cross-slot on a real cluster. As of this writing, `ordering.py` follows this convention; `messaging.py` and `cleanup_queue.py` still build keys without it — cluster support is an in-progress, subsystem-by-subsystem migration (see `_raise_cluster_not_supported` in `client.py` for the full list). Check whether a module already uses `cluster_key_prefix`/`redis_key` before assuming cluster support is complete for it.
