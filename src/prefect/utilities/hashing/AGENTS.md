# hashing

Stable hashing of strings, files, and arbitrary Python objects.

## Purpose & Scope

`stable_hash`, `file_hash`, and `hash_objects`. `hash_objects` produces the cache keys for `task_input_hash` and the `Inputs`/`FlowParameters` cache policies, and the checksums for block schemas (`Block._calculate_schema_checksum`).

## Entry Points

- `hash_objects(*args, hash_algo=..., raise_on_failure=False, **kwargs)` — hash via JSON (`JSONSerializer`, `sort_keys=True`), falling back to cloudpickle of the original objects when JSON fails.

## Contracts

- **Hashes of JSON-native inputs must not change.** Block schema checksums are persisted server-side and compared against client-computed values, so inputs made only of str-keyed dicts, lists, and scalars must keep serializing to the same JSON. `_tag_json_lossy_types` is applied to each arg and kwarg value, never to the outer `(args, kwargs)` structure, for this reason.
- **JSON-lossy types are tagged before serializing.** Tuples become `{"__tuple__": [...]}`; dicts with non-str keys (`int`, `float`, `bool`, `None`) become `{"__dict__": [[key, value], ...]}`, sorted by each key's JSON encoding. A str-keyed dict whose only key is `__tuple__` or `__dict__` is also emitted in the `__dict__` form so real values cannot collide with tagged ones. Other key types raise `TypeError` to preserve the cloudpickle fallback.
- Tagging only walks dicts, lists, and tuples. Containers nested inside objects handled by `prefect_json_object_encoder` (Pydantic models, dataclasses) are serialized by Pydantic in JSON mode and are not tagged.
