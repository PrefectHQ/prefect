import os
import warnings

import prefect.settings


def test_check_for_mismatched_environment_variables():
    """
    Checks for incorrect configuration and accidental name mismatches, e.g.

    Example:
        ❯ PREFECT_FOO=1 pytest tests/test_metachecks.py
        tests/test_metachecks.py::test_misnamed_environment_variables
        /Users/mz/dev/orion/tests/test_metachecks.py:16: UserWarning: Found unknown environment variable(s) that look Prefect settings but have no match:
                PREFECT_FOO
    """
    mismatches = []
    for key in os.environ:
        if (
            key.startswith("PREFECT_")
            and not hasattr(prefect.settings, key)
            and not key in ["PREFECT_PROFILE"]  # Explicit ignores
        ):
            mismatches.append(key)
    if mismatches:
        mismatch_string = "\n\t".join(mismatches)
        warnings.warn(
            f"Found unknown environment variable(s) that look Prefect settings but have no match:\n\t{mismatch_string}",
            stacklevel=1,
        )
