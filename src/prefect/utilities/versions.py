import re

from packaging.version import InvalidVersion, Version


def clean_version(version_string: str) -> str:
    # Remove any post-release segments
    cleaned = re.sub(r"\.post\d+", "", version_string)
    # Remove any second .dev segment
    cleaned = re.sub(r"(\.dev\d+)\.dev\d+", r"\1", cleaned)
    try:
        return str(Version(cleaned))
    except InvalidVersion:
        # If still invalid, fall back to the original string
        return version_string
