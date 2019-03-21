from prefect.core.task import Task
import prefect.tasks.core
import prefect.tasks.control_flow
import prefect.tasks.database
import prefect.tasks.github
import prefect.tasks.shell

try:
    import prefect.tasks.aws
except ImportError:
    pass

try:
    import prefect.tasks.google
except ImportError:
    pass

try:
    import prefect.tasks.kubernetes
except ImportError:
    pass

try:
    import prefect.tasks.templates
except ImportError:
    pass
