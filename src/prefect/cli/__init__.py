import sys

import prefect.settings
from prefect.cli._types import LazyTyperGroup
from prefect.cli.root import app


def _should_eager_import(argv: list[str]) -> bool:
    if len(argv) <= 1:
        return True
    return any(arg in {"-h", "--help"} for arg in argv[1:])


def _eager_import_cli() -> None:
    # Import CLI submodules to register them to the app
    # isort: split
    import prefect.cli.api
    import prefect.cli.artifact
    import prefect.cli.block
    import prefect.cli.cloud
    import prefect.cli.cloud.ip_allowlist
    import prefect.cli.cloud.webhook
    import prefect.cli.shell
    import prefect.cli.concurrency_limit
    import prefect.cli.config
    import prefect.cli.dashboard
    import prefect.cli.deploy
    import prefect.cli.deployment
    import prefect.cli.dev
    import prefect.cli.events
    import prefect.cli.experimental
    import prefect.cli.flow
    import prefect.cli.flow_run
    import prefect.cli.global_concurrency_limit
    import prefect.cli.profile
    import prefect.cli.sdk
    import prefect.cli.server
    import prefect.cli.task
    import prefect.cli.variable
    import prefect.cli.work_pool
    import prefect.cli.work_queue
    import prefect.cli.worker
    import prefect.cli.task_run
    import prefect.cli.transfer
    import prefect.events.cli.automations


_LAZY_COMMANDS: dict[str, tuple[str, ...] | str] = {
    "api": "prefect.cli.api",
    "artifact": "prefect.cli.artifact",
    "block": "prefect.cli.block",
    "blocks": "prefect.cli.block",
    "cloud": (
        "prefect.cli.cloud",
        "prefect.cli.cloud.ip_allowlist",
        "prefect.cli.cloud.webhook",
    ),
    "concurrency-limit": "prefect.cli.concurrency_limit",
    "concurrency-limits": "prefect.cli.concurrency_limit",
    "config": "prefect.cli.config",
    "dashboard": "prefect.cli.dashboard",
    "deploy": "prefect.cli.deploy",
    "init": "prefect.cli.deploy",
    "deployment": "prefect.cli.deployment",
    "deployments": "prefect.cli.deployment",
    "dev": "prefect.cli.dev",
    "event": "prefect.cli.events",
    "events": "prefect.cli.events",
    "experimental": "prefect.cli.experimental",
    "flow": "prefect.cli.flow",
    "flows": "prefect.cli.flow",
    "flow-run": "prefect.cli.flow_run",
    "flow-runs": "prefect.cli.flow_run",
    "global-concurrency-limit": "prefect.cli.global_concurrency_limit",
    "gcl": "prefect.cli.global_concurrency_limit",
    "profile": "prefect.cli.profile",
    "profiles": "prefect.cli.profile",
    "sdk": "prefect.cli.sdk",
    "server": "prefect.cli.server",
    "shell": "prefect.cli.shell",
    "task": "prefect.cli.task",
    "task-run": "prefect.cli.task_run",
    "task-runs": "prefect.cli.task_run",
    "transfer": "prefect.cli.transfer",
    "variable": "prefect.cli.variable",
    "work-pool": "prefect.cli.work_pool",
    "work-queue": "prefect.cli.work_queue",
    "work-queues": "prefect.cli.work_queue",
    "worker": "prefect.cli.worker",
    "automation": "prefect.events.cli.automations",
    "automations": "prefect.events.cli.automations",
}

if _should_eager_import(sys.argv):
    _eager_import_cli()
else:
    LazyTyperGroup.register_lazy_commands(_LAZY_COMMANDS, typer_instance=app)
