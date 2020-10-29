from prefect import context, Client


def create_link(link: str) -> str:
    """
    Create a link artifact

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - link (str): the link to post

    Returns:
        - str: the task run artifact ID
    """
    client = Client()
    return client.create_task_run_artifact(
        task_run_id=context.get("task_run_id"), kind="link", data={"link": link}
    )


def update_link(task_run_artifact_id: str, link: str) -> bool:
    """
    Update an existing link artifact. This function will replace the current link
    artifact with the new link provided.

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
        - link (str): the new link to update the artifact with

    Returns:
        - bool: whether or not the request was successful
    """
    if task_run_artifact_id is None:
        raise ValueError("The ID of an existing task run artifact must be provided.")

    client = Client()
    return client.update_task_run_artifact(
        task_run_artifact_id=task_run_artifact_id, data={"link": link}
    )


def delete_link(task_run_artifact_id: str) -> bool:
    """
    Delete an existing link artifact

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact

    Returns:
        - bool: whether or not the request was successful
    """
    if task_run_artifact_id is None:
        raise ValueError("The ID of an existing task run artifact must be provided.")

    client = Client()
    return client.delete_task_run_artifact(task_run_artifact_id=task_run_artifact_id)


def create_markdown(markdown: str) -> str:
    """
    Create a markdown artifact

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - markdown (str): the markdown to post

    Returns:
        - str: the task run artifact ID
    """
    client = Client()
    return client.create_task_run_artifact(
        task_run_id=context.get("task_run_id"),
        kind="markdown",
        data={"markdown": markdown},
    )


def update_markdown(task_run_artifact_id: str, markdown: str) -> bool:
    """
    Update an existing markdown artifact. This function will replace the current markdown
    artifact with the new markdown provided.

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
        - markdown (str): the new markdown to update the artifact with

    Returns:
        - bool: whether or not the request was successful
    """
    if task_run_artifact_id is None:
        raise ValueError("The ID of an existing task run artifact must be provided.")

    client = Client()
    return client.update_task_run_artifact(
        task_run_artifact_id=task_run_artifact_id, data={"markdown": markdown}
    )


def delete_markdown(task_run_artifact_id: str) -> bool:
    """
    Delete an existing markdown artifact

    Note: The functionality here is experimental, and may change between
    versions without notice. Use at your own risk.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact

    Returns:
        - bool: whether or not the request was successful
    """
    if task_run_artifact_id is None:
        raise ValueError("The ID of an existing task run artifact must be provided.")

    client = Client()
    return client.delete_task_run_artifact(task_run_artifact_id=task_run_artifact_id)
