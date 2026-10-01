"""
Regression test for https://github.com/PrefectHQ/prefect/issues/15869

`prefect deploy` read and wrote `prefect.yaml`, flow source files, and SLA and
trigger files with the platform's default text encoding. On Windows that is
usually cp1252, so a UTF-8 file with non-ASCII characters failed with
`'charmap' codec can't decode byte ...`, and a non-ASCII deployment name was
written in cp1252.

The default encoding is UTF-8 on most CI machines, so a plain test would pass
with or without the fix. Instead, the deploy code paths run in a subprocess
started with `-X warn_default_encoding`, which makes Python emit an
`EncodingWarning` for every text-mode open that relies on the default encoding,
on any platform.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from prefect.settings import get_current_settings

SCRIPT = textwrap.dedent(
    '''
    import asyncio
    import inspect
    import json
    import warnings
    from pathlib import Path

    import prefect

    from rich.console import Console

    from prefect.cli.deploy._commands import init
    from prefect.cli.deploy._config import _load_deploy_configs_and_actions
    from prefect.cli.deploy._sla import _gather_deployment_sla_definitions
    from prefect.cli.deploy._triggers import _gather_deployment_trigger_definitions
    from prefect.deployments.base import (
        _deployment_already_saved_to_prefect_file,
        _save_deployment_to_prefect_file,
        configure_project_by_recipe,
        create_default_prefect_yaml,
    )
    from prefect.flows import _entrypoint_definition_and_source

    name = "deploy-\\u00e9t\\u00e9-\\u65e5\\u672c"
    Path("flow.py").write_text(
        f'from prefect import flow\\n\\n\\n@flow\\ndef f():\\n    """{name}"""\\n',
        encoding="utf-8",
    )
    Path("sla.yaml").write_text(
        f"sla:\\n- name: {name}\\n  duration: 10\\n", encoding="utf-8"
    )
    Path("triggers.yaml").write_text(
        f"triggers:\\n- name: {name}\\n  enabled: true\\n", encoding="utf-8"
    )

    package_dir = Path(prefect.__file__).resolve().parent
    offenders = []


    def record(message, category, filename, lineno, file=None, line=None):
        # Only count opens made by Prefect itself. Standard library and
        # third-party modules (for example zoneinfo reading tzdata) are not ours.
        if not issubclass(category, EncodingWarning):
            return
        path = Path(filename).resolve()
        if package_dir in path.parents:
            offenders.append(f"{path.relative_to(package_dir.parent)}:{lineno}")


    warnings.simplefilter("always", EncodingWarning)
    warnings.showwarning = record


    def call(fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            if inspect.iscoroutine(result):
                asyncio.run(result)
        except SystemExit:
            pass


    create_default_prefect_yaml(
        ".", name=name, contents={"deployments": [{"name": "existing"}]}
    )
    call(_load_deploy_configs_and_actions, Path("prefect.yaml"), console=Console())
    deployment = {
        "name": name,
        "entrypoint": "flow.py:f",
        "parameter_openapi_schema": {},
    }
    _save_deployment_to_prefect_file(deployment)
    _deployment_already_saved_to_prefect_file(deployment)
    _gather_deployment_sla_definitions(["sla.yaml"], None)
    _gather_deployment_trigger_definitions(["triggers.yaml"], [])
    _entrypoint_definition_and_source("flow.py:f")
    configure_project_by_recipe("local", directory=".", name=name)
    call(init, name=name, recipe="local")

    # The written file must be UTF-8 regardless of the platform's default.
    assert name in Path("prefect.yaml").read_bytes().decode("utf-8")

    print(json.dumps(sorted(set(offenders))))
    '''
)


def test_deploy_file_io_does_not_depend_on_the_platform_encoding(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", "-c", SCRIPT],
        cwd=tmp_path,
        # Run the child with the test session's settings, not the developer's
        # own profile and PREFECT_HOME.
        env={**os.environ, **get_current_settings().to_environment_variables()},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    offenders = json.loads(result.stdout.strip().splitlines()[-1])
    assert offenders == [], (
        "These reads or writes rely on the platform's default text encoding:\n"
        + "\n".join(offenders)
    )
