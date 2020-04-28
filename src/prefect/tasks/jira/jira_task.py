from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs
from typing import cast
from typing import Any

try:
    from jira import JIRA
except ImportError:
    pass
