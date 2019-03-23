# only tasks that don't require `extras` should be automatically imported here;
# others must be explicitly imported so they can raise helpful errors if appropriate

from prefect.core.task import Task
import prefect.tasks.core
import prefect.tasks.control_flow
import prefect.tasks.database
import prefect.tasks.github
import prefect.tasks.notifications
import prefect.tasks.shell
