import os

# Check for fast CLI mode before importing anything heavy
_FAST_CLI = os.environ.get("PREFECT_CLI_FAST", "").lower() in ("1", "true")

if _FAST_CLI:
    # Fast CLI mode - use cyclopts with lazy imports
    try:
        from prefect.cli._cyclopts import app
    except ImportError as e:
        if "cyclopts" in str(e):
            raise ImportError(
                "Fast CLI mode requires cyclopts. Install with: pip install prefect[fast-cli]"
            ) from e
        raise
else:
    # Standard CLI mode - typer with eager imports
    import prefect.settings
    from prefect.cli.root import app

    # Import CLI submodules to register them to the app
    # isort: split

    import prefect.cli.api
    import prefect.cli.artifact
    import prefect.cli.block
    import prefect.cli.cloud
    import prefect.cli.cloud.asset
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
