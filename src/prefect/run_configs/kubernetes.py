import yaml
from typing import List, Union
from urllib.parse import urlparse

from .base import RunConfig


class KubernetesJob(RunConfig):
    """Configure a flow-run to run as a Kubernetes Job."""

    def __init__(
        self,
        *,
        job_template_path: str = None,
        job_template: Union[str, dict] = None,
        image: str = None,
        env: dict = None,
        cpu_limit: str = None,
        cpu_request: str = None,
        memory_limit: str = None,
        memory_request: str = None,
        labels: List[str] = None,
    ) -> None:
        super().__init__(labels=labels)
        if job_template_path is not None and job_template is not None:
            raise ValueError(
                "Cannot provide both `job_template_path` and `job_template`"
            )
        if job_template_path is not None:
            parsed = urlparse(job_template_path)
            # If it's a local file, load now rather than runtime
            if not parsed.scheme or parsed.scheme in ("local", "file"):
                with open(parsed.path) as f:
                    job_template = yaml.safe_load(f)
                    job_template_path = None
        elif job_template is not None:
            # Normalize job templates to objects rather than str
            if isinstance(job_template, str):
                job_template = yaml.safe_load(job_template)

        self.job_template_path = job_template_path
        self.job_template = job_template
        self.image = image
        self.env = env
        self.memory_limit = memory_limit
        self.memory_request = memory_request
        self.cpu_limit = cpu_limit
        self.cpu_request = cpu_request
