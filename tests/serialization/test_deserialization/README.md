# Testing Deserialization

It is important for Prefect to maintain backwards-compatibility with older versions of Prefect by ensuring that objects serialized under older versions can be deserialized under newer ones.

These tests use snapshots of objects from older versions to ensure compatibility as the Schemas evolve.
