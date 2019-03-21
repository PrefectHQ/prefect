from prefect.tasks.kubernetes.deployment import (
    CreateNamespacedDeployment,
    DeleteNamespacedDeployment,
    ListNamespacedDeployment,
    PatchNamespacedDeployment,
    ReadNamespacedDeployment,
    ReplaceNamespacedDeployment,
)
from prefect.tasks.kubernetes.job import (
    CreateNamespacedJob,
    DeleteNamespacedJob,
    ListNamespacedJob,
    PatchNamespacedJob,
    ReadNamespacedJob,
    ReplaceNamespacedJob,
)
from prefect.tasks.kubernetes.pod import CreateNamespacedPodTask
from prefect.tasks.kubernetes.service import CreateNamespacedServiceTask
