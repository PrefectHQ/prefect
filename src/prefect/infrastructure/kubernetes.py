import enum
from typing import TYPE_CHECKING, Any, Dict, Optional

import yaml
from jsonpatch import JsonPatch
from pydantic import Field
from typing_extensions import Literal

from prefect.blocks.kubernetes import KubernetesClusterConfig
from prefect.flow_runners.base import get_prefect_image_name
from prefect.infrastructure.base import Infrastructure
from prefect.utilities.importtools import lazy_import

if TYPE_CHECKING:
    import kubernetes
    import kubernetes.client
    import kubernetes.config
else:
    kubernetes = lazy_import("kubernetes")
    kubernetes.config = lazy_import("kubernetes.config")
    kubernetes.client = lazy_import("kubernetes.client")
    kubernetes.watch = lazy_import("kubernetes.watch")


class KubernetesImagePullPolicy(enum.Enum):
    IF_NOT_PRESENT = "IfNotPresent"
    ALWAYS = "Always"
    NEVER = "Never"


class KubernetesRestartPolicy(enum.Enum):
    ON_FAILURE = "OnFailure"
    NEVER = "Never"


KubernetesManifest = Dict[str, Any]


class KubernetesJob(Infrastructure):
    type: Literal["kubernetes-job"] = "kubernetes-job"

    # shortcuts for the most common user-serviceable settings
    image: str = Field(default_factory=get_prefect_image_name)
    namespace: str = "default"
    service_account_name: str = None
    labels: Dict[str, str] = Field(default_factory=dict)
    image_pull_policy: Optional[KubernetesImagePullPolicy] = None

    # settings allowing full customization of the Job
    job: KubernetesManifest = Field(
        default_factory=lambda: KubernetesJob.base_job_manifest()
    )
    customizations: JsonPatch = Field(default_factory=lambda: JsonPatch([]))

    # controls the behavior of the FlowRunner
    job_watch_timeout_seconds: int = 5
    pod_watch_timeout_seconds: int = 60
    stream_output: bool = True
    cluster_config: KubernetesClusterConfig = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {JsonPatch: lambda p: p.patch}

    @classmethod
    def base_job_manifest(cls) -> KubernetesManifest:
        """Produces the bare minimum allowed Job manifest"""
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"labels": {}},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            }
                        ]
                    }
                }
            },
        }

    # Note that we're using the yaml package to load both YAML and JSON files below.
    # This works because YAML is a strict superset of JSON:
    #
    #   > The YAML 1.23 specification was published in 2009. Its primary focus was
    #   > making YAML a strict superset of JSON. It also removed many of the problematic
    #   > implicit typing recommendations.
    #
    #   https://yaml.org/spec/1.2.2/#12-yaml-history

    @classmethod
    def job_from_file(cls, filename: str) -> KubernetesManifest:
        """Load a Kubernetes Job manifest from a YAML or JSON file."""
        with open(filename, "r", encoding="utf-8") as f:
            return yaml.load(f, yaml.SafeLoader)

    @classmethod
    def customize_from_file(cls, filename: str) -> JsonPatch:
        """Load an RFC 6902 JSON patch from a YAML or JSON file."""
        with open(filename, "r", encoding="utf-8") as f:
            return JsonPatch(yaml.load(f, yaml.SafeLoader))

    def _shortcut_customizations(self) -> JsonPatch:
        """Produces the JSON 6902 patch for the most commonly used customizations, like
        image and namespace, which we offer as top-level parameters (with sensible
        default values)"""
        shortcuts = [
            {
                "op": "add",
                "path": "/metadata/namespace",
                "value": self.namespace,
            },
            {
                "op": "add",
                "path": "/spec/template/spec/containers/0/image",
                "value": self.image,
            },
        ]

        shortcuts += [
            {
                "op": "add",
                "path": f"/metadata/labels/{key}",
                "value": value,
            }
            for key, value in self.labels.items()
        ]

        if self.image_pull_policy:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/imagePullPolicy",
                    "value": self.image_pull_policy.value,
                }
            )

        if self.service_account_name:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/spec/template/spec/serviceAccountName",
                    "value": self.service_account_name,
                }
            )

        return JsonPatch(shortcuts)
