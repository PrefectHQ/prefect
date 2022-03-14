from prefect.cli.base import app

# Import CLI submodules to register them to the app
import prefect.cli.deployment
import prefect.cli.concurrency_limit
import prefect.cli.agent
import prefect.cli.flow_run
import prefect.cli.orion
import prefect.cli.config
import prefect.cli.dev
import prefect.cli.profile
import prefect.cli.storage
import prefect.cli.cloud
import prefect.cli.work_queue
