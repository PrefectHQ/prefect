import toml

import prefect
from prefect._internal.integrations import KNOWN_EXTRAS_FOR_PACKAGES


def test_known_extras_for_packages():
    pyproject_contents = toml.load(prefect.__development_base_path__ / "pyproject.toml")

    # Extract the extras_require dictionary
    extras_require = pyproject_contents["project"]["optional-dependencies"]

    # Check each entry in known_extras
    for package, extra in KNOWN_EXTRAS_FOR_PACKAGES.items():
        extra_name = extra.split("[")[1][:-1]
        assert extra_name in extras_require, (
            f"Extra '{extra_name}' for package '{package}' not found in setup.py"
        )
