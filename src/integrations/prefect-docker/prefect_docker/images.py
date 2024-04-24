"""Integrations with Docker Images."""

from typing import Any, Dict, List, Optional, Union

from docker.models.images import Image

from prefect import get_run_logger, task
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect_docker.credentials import DockerRegistryCredentials
from prefect_docker.host import DockerHost


@task
async def pull_docker_image(
    repository: str,
    tag: Optional[str] = None,
    platform: Optional[str] = None,
    all_tags: bool = False,
    docker_host: Optional[DockerHost] = None,
    docker_registry_credentials: Optional[DockerRegistryCredentials] = None,
    **pull_kwargs: Dict[str, Any],
) -> Union[Image, List[Image]]:
    """
    Pull an image of the given name and return it. Similar to the docker pull command.

    If all_tags is set, the tag parameter is ignored and all image tags will be pulled.

    Args:
        repository: The repository to pull.
        tag: The tag to pull; if not provided, it is set to latest.
        platform: Platform in the format os[/arch[/variant]].
        all_tags: Pull all image tags which will return a list of Images.
        docker_host: Settings for interacting with a Docker host; if not
            provided, will automatically instantiate a `DockerHost` from env.
        docker_registry_credentials: Docker credentials used to log in to
            a registry before pulling the image.
        **pull_kwargs: Additional keyword arguments to pass to `client.images.pull`.

    Returns:
        The image that has been pulled, or a list of images if `all_tags` is `True`.

    Examples:
        Pull prefecthq/prefect image with the tag latest-python3.10.
        ```python
        from prefect import flow
        from prefect_docker.images import pull_docker_image

        @flow
        def pull_docker_image_flow():
            image = pull_docker_image(
                repository="prefecthq/prefect",
                tag="latest-python3.10"
            )
            return image

        pull_docker_image_flow()
        ```
    """
    logger = get_run_logger()
    if tag and all_tags:
        raise ValueError("Cannot pass `tags` and `all_tags` together")

    pull_kwargs = {
        "repository": repository,
        "tag": tag,
        "platform": platform,
        "all_tags": all_tags,
        **pull_kwargs,
    }
    pull_kwargs = {
        key: value for key, value in pull_kwargs.items() if value is not None
    }

    with (docker_host or DockerHost()).get_client() as client:
        if docker_registry_credentials is not None:
            await docker_registry_credentials.login(client=client)

        if tag:
            logger.info(f"Pulling image: {repository}:{tag}.")
        elif all_tags:
            logger.info(f"Pulling all images from: {repository}")

        image = await run_sync_in_worker_thread(client.images.pull, **pull_kwargs)

    return image
