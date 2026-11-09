# hashing

Stable hashing of strings, files, and arbitrary Python objects.

## Purpose & Scope

`stable_hash`, `file_hash`, and `hash_objects`. `hash_objects` produces the cache keys for `task_input_hash` and the `Inputs`/`FlowParameters` cache policies, and the checksums for block schemas (`Block._calculate_schema_checksum`).

## Entry Points

- `hash_objects(*args, hash_algo=..., raise_on_failure=False, **kwargs)` — hash via JSON (`JSONSerializer`, `sort_keys=True`), falling back to cloudpickle of the original objects when JSON fails.

## Contracts

- **Hashes of JSON-native inputs must not change.** Block schema checksums are persisted server-side and compared against client-computed values, so inputs made only of str-keyed dicts, lists, and scalars must keep serializing to the same JSON. When no tuple or non-str-key dict is found, `hash_objects` hashes the untagged `(args, kwargs)` exactly as before; this includes str-keyed dicts that happen to use the `__tuple__`/`__dict__` tag names.
- **JSON-lossy types are tagged before serializing.** When a tuple or non-str-key dict is present, tuples become `{"__tuple__": [...]}` and dicts with non-str keys (`int`, `float`, `bool`, `None`) become `{"__dict__": [[key, value], ...]}`, sorted by each key's JSON encoding. The tagged JSON is hashed with a `\x00` prefix, which JSON output can never start with, so tagged hashes can't collide with untagged ones. Within a tagged payload, a str-keyed dict whose only key is `__tuple__` or `__dict__` is escaped into the `__dict__` form so real values can't collide with tags. Other key types raise `TypeError` to preserve the cloudpickle fallback.
- Tagging only walks dicts, lists, and tuples. Containers nested inside objects handled by `prefect_json_object_encoder` (Pydantic models, dataclasses) are serialized by Pydantic in JSON mode and are not tagged.
