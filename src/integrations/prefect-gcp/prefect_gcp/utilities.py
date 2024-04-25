from typing import Optional

from slugify import slugify


def slugify_name(name: str, max_length: int = 30) -> Optional[str]:
    """
    Slugify text for use as a name.

    Keeps only alphanumeric characters and dashes, and caps the length
    of the slug at 30 chars.

    The 30 character length allows room to add a uuid for generating a unique
    name for the job while keeping the total length of a name below 63 characters,
    which is the limit for Cloud Run job names.

    Args:
        name: The name of the job

    Returns:
        The slugified job name or None if the slugified name is empty
    """
    slug = slugify(
        name,
        max_length=max_length,
        regex_pattern=r"[^a-zA-Z0-9-]+",
    )

    return slug if slug else None
