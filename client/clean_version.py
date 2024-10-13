import re

from packaging.version import InvalidVersion, Version

import prefect


def clean_version(version_string: str) -> str:
    # Remove any post-release segments
    cleaned = re.sub(r"\.post\d+", "", version_string)
    # Remove any dev segments
    cleaned = re.sub(r"\.dev\d+", "", cleaned)
    try:
        return str(Version(cleaned))
    except InvalidVersion:
        # If still invalid, fall back to the original string
        return version_string


if __name__ == "__main__":
    print(clean_version(prefect.__version__))
