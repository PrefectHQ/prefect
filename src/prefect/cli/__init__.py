import prefect.settings
from prefect._internal.compatibility.experimental import experiment_enabled
from prefect.cli.root import app

# Import CLI submodules to register them to the app
# isort: split

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
import prefect.cli.flow
import prefect.cli.flow_run
import prefect.cli.global_concurrency_limit
import prefect.cli.profile
import prefect.cli.server
import prefect.cli.task
import prefect.cli.variable
import prefect.cli.work_pool
import prefect.cli.work_queue
import prefect.cli.worker
import prefect.cli.task_run
import prefect.events.cli.automations
