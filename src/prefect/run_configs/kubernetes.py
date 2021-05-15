from typing import Union, Iterable

import yaml

from prefect.run_configs.base import RunConfig
from prefect.utilities.filesystems import parse_path


class KubernetesRun(RunConfig):
    """Configure a flow-run to run as a Kubernetes Job.

    Kubernetes jobs are configured by filling in a job template at runtime. A
    job template can be specified either as a path (to be read in at runtime)
    or an in-memory object (which will be stored along with the flow in Prefect
    Cloud/Server). By default the job template configured on the Agent is used.

    Args:
        - job_template_path (str, optional): Path to a job template to use. If
            a local path (no file scheme, or a `file`/`local` scheme), the job
            template will be loaded on initialization and stored on the
            `KubernetesRun` object as the `job_template` field.  Otherwise the
            job template will be loaded at runtime on the agent.  Supported
            runtime file schemes include (`s3`, `gcs`, and `agent` (for paths
            local to the runtime agent)).
        - job_template (str or dict, optional): An in-memory job template to
            use. Can be either a dict, or a YAML string.
        - image (str, optional): The image to use
        - env (dict, optional): Additional environment variables to set on the job
        - cpu_limit (float or str, optional): The CPU limit to use for the job
        - cpu_request (float or str, optional): The CPU request to use for the job
        - memory_limit (str, optional): The memory limit to use for the job
        - memory_request (str, optional): The memory request to use for the job
        - service_account_name (str, optional): A service account name to use
            for this job. If present, overrides any service account configured
            on the agent or in the job template.
        - image_pull_secrets (list, optional): A list of image pull secrets to
            use for this job. If present, overrides any image pull secrets
            configured on the agent or in the job template.
        - labels (Iterable[str], optional): an iterable of labels to apply to this
            run config. Labels are string identifiers used by Prefect Agents
            for selecting valid flow runs when polling for work
        - image_pull_policy (str, optional): The imagePullPolicy to use for the job.
            https://kubernetes.io/docs/concepts/configuration/overview/#container-images

    Examples:

    Use the defaults set on the agent:

    ```python
    flow.run_config = KubernetesRun()
    ```

    Use a local job template, which is stored along with the Flow in Prefect
    Cloud/Server:

    ```python
    flow.run_config = KubernetesRun(
        job_template_path="my_custom_template.yaml"
    )
    ```

    Use a job template stored in S3, but override the image and CPU limit:

    ```python
    flow.run_config = KubernetesRun(
        job_template_path="s3://example-bucket/my_custom_template.yaml",
        image="example/my-custom-image:latest",
        cpu_limit=2,
    )
    ```

    Use an image not tagged with :latest, and set the image pull policy to `Always`:

    ```python
    flow.run_config = KubernetesRun(
        image="example/my-custom-image:my-tag,
        image_pull_policy="Always"
    )
    ```
    """

    def __init__(
        self,
        *,
        job_template_path: str = None,
        job_template: Union[str, dict] = None,
        image: str = None,
        env: dict = None,
        cpu_limit: Union[float, str] = None,
        cpu_request: Union[float, str] = None,
        memory_limit: str = None,
        memory_request: str = None,
        service_account_name: str = None,
        image_pull_secrets: Iterable[str] = None,
        labels: Iterable[str] = None,
        image_pull_policy: str = None,
    ) -> None:
        super().__init__(env=env, labels=labels)
        if job_template_path is not None and job_template is not None:
            raise ValueError(
                "Cannot provide both `job_template_path` and `job_template`"
            )
        if job_template_path is not None:
            parsed = parse_path(job_template_path)
            if parsed.scheme == "file":
                with open(parsed.path) as f:
                    job_template = yaml.safe_load(f)
                    job_template_path = None
        elif job_template is not None:
            # Normalize job templates to objects rather than str
            if isinstance(job_template, str):
                job_template = yaml.safe_load(job_template)

        assert job_template is None or isinstance(job_template, dict)  # mypy

        if cpu_limit is not None:
            cpu_limit = str(cpu_limit)
        if cpu_request is not None:
            cpu_request = str(cpu_request)

        if image_pull_secrets is not None:
            image_pull_secrets = list(image_pull_secrets)

        image_pull_policies = {"Always", "IfNotPresent", "Never"}
        if (
            image_pull_policy is not None
            and image_pull_policy not in image_pull_policies
        ):
            raise ValueError(
                f"Invalid image_pull_policy {image_pull_policy!r}.  "
                "Expected 'Always', 'IfNotPresent', or 'Never'"
            )

        self.job_template_path = job_template_path
        self.job_template = job_template
        self.image = image
        self.cpu_limit = cpu_limit
        self.cpu_request = cpu_request
        self.memory_limit = memory_limit
        self.memory_request = memory_request
        self.service_account_name = service_account_name
        self.image_pull_secrets = image_pull_secrets
        self.image_pull_policy = image_pull_policy
