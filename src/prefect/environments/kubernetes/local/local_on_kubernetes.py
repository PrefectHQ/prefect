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

    # Override build, make a build_image which has all the logic,
    # build must return a type of the environment that is is subclassed from
    def execute(self) -> None:
        pass

    def run(self) -> None:
        pass

    def setup(self) -> None:
        pass

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

        image_name = str(uuid.uuid4())
        image_tag = str(uuid.uuid4())

        with tempfile.TemporaryDirectory() as tempdir:

            self.pull_image()

            self.create_dockerfile(flow=flow, directory=tempdir)

            client = docker.APIClient(base_url="unix://var/run/docker.sock")

            if self.registry_url:
                full_name = os.path.join(self.registry_url, image_name)
            elif push is True:
                raise ValueError(
                    "This environment has no `registry_url`, and cannot be pushed."
                )
            else:
                full_name = image_name

            logging.info("Building the flow's container environment...")
            output = client.build(
                path=tempdir, tag="{}:{}".format(full_name, image_tag), forcerm=True
            )
            self._parse_generator_output(output)

            if push:
                self.push_image(full_name, image_tag)

                # Remove the image locally after being pushed
                client.remove_image(
                    image="{}:{}".format(full_name, image_tag), force=True
                )

            return LocalOnKubernetesEnvironment(
                base_image=self.base_image,
                registry_url=self.registry_url,
                image_name=image_name,
                image_tag=image_tag,
                python_dependencies=self.python_dependencies,
            )
