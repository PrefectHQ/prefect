from __future__ import annotations

import socket
from uuid import uuid4


def generate_consumer_name() -> str:
    """Return a unique name for Redis stream consumers."""
    return f"{socket.gethostname()}-{uuid4().hex}"
