def should_redact_header(key: str) -> bool:
    """Indicates whether an HTTP header is sensitive or noisy and should be redacted
    from events and templates."""
    key = key.lower()
    if key in {"authorization", "traceparent", "via"}:
        return True
    if key.startswith("x-forwarded"):
        return True
    if key.startswith("x-b3"):
        return True
    if key.startswith("x-cloud-trace"):
        return True
    if key.startswith("x-envoy"):
        return True
    if key.startswith("x-prefect"):
        return True

    return False
