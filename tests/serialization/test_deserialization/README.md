# Testing Deserialization

It is important for Prefect to maintain backwards-compatibility with older version of Prefect by ensuring that objects serialized under olde versions can be deserialized under newer ones.

These tests use snapshots of objects from oderl versions to ensure compatibility as the Schemas evolve.
