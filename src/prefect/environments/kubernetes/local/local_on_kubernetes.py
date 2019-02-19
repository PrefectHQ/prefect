import prefect
from prefect.environments import DockerEnvironment
import filecmp
import json
import logging
import os
import shutil
import tempfile
import textwrap
from typing import Iterable
import uuid

import docker


class LocalOnKubernetesEnvironment(DockerEnvironment):
    """"""

    def __init__(
        self,
        base_image: str = "python:3.6",
        registry_url: str = None,
        python_dependencies: list = None,
        image_name: str = None,
        image_tag: str = None,
        env_vars: dict = None,
        files: dict = None,
    ) -> None:
        super().__init__(
            base_image=base_image,
            registry_url=registry_url,
            python_dependencies=python_dependencies,
            image_name=image_name,
            image_tag=image_tag,
            env_vars=env_vars,
            files=files,
        )

    def execute(self) -> None:
        print("execute")

    def run(self) -> None:
        pass

    def setup(self) -> None:
        print("setup")

    def build(
        self, flow: "prefect.Flow", push: bool = True
    ) -> "prefect.environments.DockerEnvironment":
        """
        Build the Docker container. Returns a Container Environment with the appropriate
        image_name and image_tag set.

        Args:
            - flow (prefect.Flow): Flow to be placed in container
            - push (bool): Whether or not to push to registry after build

        Returns:
            - DockerEnvironment: a DockerEnvironment that represents the provided flow.
        """

        image_name, image_tag = self.build_image(flow=flow, push=push)

        return LocalOnKubernetesEnvironment(
            base_image=self.base_image,
            registry_url=self.registry_url,
            image_name=image_name,
            image_tag=image_tag,
        )
