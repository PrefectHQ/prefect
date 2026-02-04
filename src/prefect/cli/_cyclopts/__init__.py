"""
Prefect CLI powered by cyclopts.

This is the new CLI implementation being migrated from typer to cyclopts.
Enable with PREFECT_CLI_FAST=1 during the migration period.

Commands not yet migrated will delegate to the existing typer implementation.
"""

import sys

import cyclopts


# Lazy version lookup - only imports prefect when needed
def _get_version() -> str:
    import prefect

    return prefect.__version__


app = cyclopts.App(
    name="prefect",
    help="Prefect CLI for workflow orchestration.",
    version=_get_version,
)


def _not_implemented(command: str):
    """Show error for commands not yet migrated to cyclopts."""
    print(
        f"Command '{command}' is not yet migrated to the new CLI.\n"
        f"Run without PREFECT_CLI_FAST=1 to use this command.",
        file=sys.stderr,
    )
    sys.exit(1)


# =============================================================================
# Command groups - each delegates to real implementation when executed
# =============================================================================

# --- deploy ---
deploy_app = cyclopts.App(name="deploy", help="Create and manage deployments.")
app.command(deploy_app)


@deploy_app.default
def deploy_default(*tokens: str):
    """Deploy flows. Run 'prefect deploy --help' for options."""
    from prefect.cli.deploy import deploy

    # Re-invoke with typer
    from prefect.cli.root import app as typer_app

    typer_app(["deploy"] + list(tokens), standalone_mode=False)


# --- flow-run ---
flow_run_app = cyclopts.App(name="flow-run", help="Interact with flow runs.")
app.command(flow_run_app)


@flow_run_app.default
def flow_run_default(*tokens: str):
    """Manage flow runs."""
    from prefect.cli.flow_run import flow_run_app as typer_flow_run
    from prefect.cli.root import app as typer_app

    typer_app(["flow-run"] + list(tokens), standalone_mode=False)


# --- worker ---
worker_app = cyclopts.App(name="worker", help="Start and interact with workers.")
app.command(worker_app)


@worker_app.default
def worker_default(*tokens: str):
    """Manage workers."""
    from prefect.cli.worker import worker_app as typer_worker
    from prefect.cli.root import app as typer_app

    typer_app(["worker"] + list(tokens), standalone_mode=False)


# --- block ---
block_app = cyclopts.App(name="block", help="Interact with blocks.")
app.command(block_app)


@block_app.default
def block_default(*tokens: str):
    """Manage blocks."""
    from prefect.cli.block import block_app as typer_block
    from prefect.cli.root import app as typer_app

    typer_app(["block"] + list(tokens), standalone_mode=False)


# --- config (native cyclopts) ---
from prefect.cli._cyclopts.config import config_app

app.command(config_app)


# --- profile ---
profile_app = cyclopts.App(name="profile", help="Manage Prefect profiles.")
app.command(profile_app)


@profile_app.default
def profile_default(*tokens: str):
    """Manage profiles."""
    from prefect.cli.profile import profile_app as typer_profile
    from prefect.cli.root import app as typer_app

    typer_app(["profile"] + list(tokens), standalone_mode=False)


# --- server ---
server_app = cyclopts.App(name="server", help="Start and manage the Prefect server.")
app.command(server_app)


@server_app.default
def server_default(*tokens: str):
    """Manage server."""
    from prefect.cli.server import server_app as typer_server
    from prefect.cli.root import app as typer_app

    typer_app(["server"] + list(tokens), standalone_mode=False)


# --- cloud ---
cloud_app = cyclopts.App(name="cloud", help="Interact with Prefect Cloud.")
app.command(cloud_app)


@cloud_app.default
def cloud_default(*tokens: str):
    """Manage cloud."""
    from prefect.cli.cloud import cloud_app as typer_cloud
    from prefect.cli.root import app as typer_app

    typer_app(["cloud"] + list(tokens), standalone_mode=False)


# --- work-pool ---
work_pool_app = cyclopts.App(name="work-pool", help="Manage work pools.")
app.command(work_pool_app)


@work_pool_app.default
def work_pool_default(*tokens: str):
    """Manage work pools."""
    from prefect.cli.work_pool import work_pool_app as typer_work_pool
    from prefect.cli.root import app as typer_app

    typer_app(["work-pool"] + list(tokens), standalone_mode=False)


# --- variable ---
variable_app = cyclopts.App(name="variable", help="Manage Prefect variables.")
app.command(variable_app)


@variable_app.default
def variable_default(*tokens: str):
    """Manage variables."""
    from prefect.cli.variable import variable_app as typer_variable
    from prefect.cli.root import app as typer_app

    typer_app(["variable"] + list(tokens), standalone_mode=False)


# =============================================================================
# Less common commands - show "not implemented" for now
# =============================================================================


@app.command(name="api")
def api_cmd(*tokens: str):
    """Interact with the Prefect API."""
    _not_implemented("api")


@app.command(name="artifact")
def artifact_cmd(*tokens: str):
    """Manage artifacts."""
    _not_implemented("artifact")


@app.command(name="concurrency-limit")
def concurrency_limit_cmd(*tokens: str):
    """Manage concurrency limits."""
    _not_implemented("concurrency-limit")


@app.command(name="dashboard")
def dashboard_cmd(*tokens: str):
    """Open the Prefect dashboard."""
    _not_implemented("dashboard")


@app.command(name="deployment")
def deployment_cmd(*tokens: str):
    """Manage deployments (legacy)."""
    _not_implemented("deployment")


@app.command(name="dev")
def dev_cmd(*tokens: str):
    """Development commands."""
    _not_implemented("dev")


@app.command(name="events")
def events_cmd(*tokens: str):
    """Manage events."""
    _not_implemented("events")


@app.command(name="flow")
def flow_cmd(*tokens: str):
    """Manage flows."""
    _not_implemented("flow")


@app.command(name="global-concurrency-limit")
def global_concurrency_limit_cmd(*tokens: str):
    """Manage global concurrency limits."""
    _not_implemented("global-concurrency-limit")


@app.command(name="shell")
def shell_cmd(*tokens: str):
    """Start an interactive shell."""
    _not_implemented("shell")


@app.command(name="task")
def task_cmd(*tokens: str):
    """Manage tasks."""
    _not_implemented("task")


@app.command(name="task-run")
def task_run_cmd(*tokens: str):
    """Manage task runs."""
    _not_implemented("task-run")


@app.command(name="work-queue")
def work_queue_cmd(*tokens: str):
    """Manage work queues."""
    _not_implemented("work-queue")


@app.command(name="automations")
def automations_cmd(*tokens: str):
    """Manage automations."""
    _not_implemented("automations")


@app.command(name="transfer")
def transfer_cmd(*tokens: str):
    """Transfer resources between workspaces."""
    _not_implemented("transfer")


# =============================================================================
# Top-level version command (separate from --version flag)
# =============================================================================


@app.command(name="version")
def version_cmd():
    """Display detailed version information."""
    # This one is common enough to implement directly
    from prefect.cli.root import app as typer_app

    typer_app(["version"], standalone_mode=False)
