"""Reproducer for a cyclopts runner state leak that makes a sequence of
`CycloptsCliRunner.invoke(...)` calls behave differently from individual calls.

Observed symptom
----------------
Three tests in `tests/cli/deploy/test_deploy_versioning.py` pass when run in
isolation but fail when run as a group::

    uv run pytest tests/cli/deploy/test_deploy_versioning.py
    FAILED tests/cli/deploy/test_deploy_versioning.py::test_deploy_with_inferred_version
    FAILED tests/cli/deploy/test_deploy_versioning.py::test_deploy_with_inferred_version_and_version_name
    FAILED tests/cli/deploy/test_deploy_versioning.py::test_deploy_with_simple_type_and_no_version_uses_flow_version

The captured stderr on the second-and-subsequent failures is::

    ╭─ Error ─────────────────────────╮
    │ Unknown option: "-n".           │
    ╰─────────────────────────────────╯

i.e. cyclopts no longer recognizes the `-n` alias on `deploy --name`. The
alias is clearly registered -- it works on the first invocation of the
process and in isolation.

The minimal reproduction in this module strips everything back to:

1. invoke `prefect deploy --help` once (which triggers cyclopts lazy-loading
   of `prefect.cli.deploy.deploy_app`),
2. invoke `prefect deploy ./x.py:f -n x -p p` -- which now fails parsing.

Hypothesis
----------
`CommandSpec.resolve()` in cyclopts caches the imported App on first access
and returns the cached instance thereafter. Something about the help-flag
show-state mutation at the end of `resolve()`, or cyclopts' parameter
parsing caching, is leaving the resolved deploy app in a state where later
token parses no longer see the `-n` alias. Needs someone familiar with
cyclopts internals to confirm.

Both `CycloptsCliRunner.invoke` and `prefect.cli._app._app.meta` are
plausible fix sites; this test is strictly a reproducer.

Marked xfail so the rest of the suite is unaffected; remove the marker
once the leak is fixed.
"""

from __future__ import annotations

import pytest

from prefect.testing.cli import CycloptsCliRunner


@pytest.mark.xfail(
    reason=(
        "cyclopts runner state leak: second `deploy` invocation loses the "
        "`-n` alias after a prior `deploy --help` call in the same process"
    ),
    strict=True,
)
def test_deploy_n_alias_survives_prior_invocation():
    """First invocation: `deploy --help` (clean exit, triggers lazy load).
    Second invocation: `deploy ... -n NAME ...` should still parse `-n`.

    Currently fails: cyclopts reports `Unknown option: "-n".` on the second
    call even though the first call left exit_code=0 and the alias is
    defined exactly once in `src/prefect/cli/deploy/_commands.py`.
    """
    # Cleanly triggers lazy load of the deploy subcommand.
    first = CycloptsCliRunner().invoke(["deploy", "--help"])
    assert first.exit_code == 0

    # Same process, second invocation. We don't care whether deploy
    # *succeeds* here -- no workpool, no flow file -- we only care that
    # cyclopts parses the flags. If this regresses into "Unknown option:
    # -n", the leak is back.
    second = CycloptsCliRunner().invoke(
        ["deploy", "./does_not_matter.py:f", "-n", "my-name", "-p", "some-pool"]
    )
    stderr_text = second.stderr or ""
    # The check we actually care about: the parser must have accepted the
    # tokens, regardless of subsequent failures in the command body.
    assert "Unknown option" not in stderr_text, (
        f"cyclopts lost an alias across invocations; stderr: {stderr_text[:300]!r}"
    )
