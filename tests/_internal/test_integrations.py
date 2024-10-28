import re

import prefect
from prefect._internal.integrations import KNOWN_EXTRAS_FOR_PACKAGES


def extract_extras_require(setup_py_content):
    # Use regular expressions to find the extras_require dictionary
    match = re.search(r"extras_require\s*=\s*(\{.*?\})", setup_py_content, re.DOTALL)
    if match:
        extras_require_str = match.group(1)
        # Define the context for eval
        client_requires = []
        install_requires = []
        dev_requires = []
        markdown_requirements = []
        markdown_tests_requires = []

        # Evaluate the dictionary string to a Python dictionary
        extras_require = eval(
            extras_require_str,
            {
                "client_requires": client_requires,
                "install_requires": install_requires,
                "dev_requires": dev_requires,
                "markdown_requirements": markdown_requirements,
                "markdown_tests_requires": markdown_tests_requires,
            },
        )
        return extras_require
    return {}


def test_known_extras_for_packages():
    setup_py_contents = (prefect.__development_base_path__ / "setup.py").read_text()

    # Extract the extras_require dictionary
    extras_require = extract_extras_require(setup_py_contents)

    # Check each entry in known_extras
    for package, extra in KNOWN_EXTRAS_FOR_PACKAGES.items():
        extra_name = extra.split("[")[1][:-1]
        assert (
            extra_name in extras_require
        ), f"Extra '{extra_name}' for package '{package}' not found in setup.py"
