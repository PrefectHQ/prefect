import os
import socket
import uuid


def generate_unique_consumer_name(group_name: str) -> str:
    """
    Generates a unique consumer name for a given group.

    The name is composed of the group name, hostname, process ID, and a short UUID
    to ensure uniqueness across different machines and processes.

    Args:
        group_name: The logical group name for the consumer.

    Returns:
        A unique string to be used as the consumer name.
    """
    hostname = socket.gethostname()
    pid = os.getpid()
    short_uuid = uuid.uuid4().hex[:8]
    return f"{group_name}-{hostname}-{pid}-{short_uuid}"
