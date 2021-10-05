from prefect.cli.base import app

# Import CLI submodules to register them to the app
import prefect.cli.deployment
import prefect.cli.agent
import prefect.cli.flow_run
import prefect.cli.orion
import prefect.cli.dev
