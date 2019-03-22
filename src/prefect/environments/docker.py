import filecmp
import json
import logging
import os
import shutil
import tempfile
import textwrap
from typing import Iterable, List
import uuid

import docker

import prefect
from prefect.environments import Environment
from prefect.environments import LocalEnvironment
from prefect.utilities.exceptions import SerializationError


class DockerEnvironment(Environment):
    """
    This is a base environment which takes a flow, serializes it into a LocalEnvironment,
    and places it inside of a Docker image. This image is then used in any environment
    which depends on using Docker containers (e.g. the Kubernetes environments).

    Args:
        - base_image (string): the base image for this environment (e.g. `python:3.6`)
        - registry_url (string, optional): URL of a registry to push the image to; image will not be pushed if not provided
        - python_dependencies (List[str], optional): list of pip installable dependencies for the image
        - image_name (string, optional): name of the image to use when building, defaults to a UUID
        - image_tag (string, optional): tag of the image to use when building, defaults to a UUID
        - env_vars (dict, optional): a dictionary of environment variables to use when building
        - files (dict, optional): a dictionary of files to copy into the image when building
    """

    def __init__(
        self,
        base_image: str,
        registry_url: str = None,
        python_dependencies: List[str] = None,
        image_name: str = None,
        image_tag: str = None,
        env_vars: dict = None,
        files: dict = None,
    ) -> None:
        self.base_image = base_image
        self.registry_url = registry_url
        self.image_name = image_name
        self.image_tag = image_tag
        self.python_dependencies = python_dependencies or []
        self.env_vars = env_vars or {}
        self.files = files or {}
        not_absolute = [
            file_path for file_path in self.files if not os.path.isabs(file_path)
        ]
        if not_absolute:
            raise ValueError(
                "Provided paths {} are not absolute file paths, please provide absolute paths only.".format(
                    ", ".join(not_absolute)
                )
            )

    def _parse_generator_output(self, generator: Iterable) -> None:
        """
        Parses and writes a Docker command's output to stdout
        """
        for item in generator:
            item = item.decode("utf-8")
            for line in item.split("\n"):
                if line:
                    output = json.loads(line).get("stream")
                    if output and output != "\n":
                        print(output.strip("\n"))

    def build(
        self, flow: "prefect.Flow", push: bool = True
    ) -> "prefect.environments.DockerEnvironment":
        """
        Build the Docker image. Returns a DockerEnvironment with the appropriate
        image_name and image_tag set.

        Args:
            - flow (prefect.Flow): Flow to be placed the image
            - push (bool): Whether or not to push to registry after build

        Returns:
            - DockerEnvironment: a DockerEnvironment that represents the provided flow.
        """

        image_name, image_tag = self.build_image(flow=flow, push=push)

        return DockerEnvironment(
            base_image=self.base_image,
            registry_url=self.registry_url,
            image_name=image_name,
            image_tag=image_tag,
        )

    def build_image(self, flow: "prefect.Flow", push: bool = True) -> tuple:
        """
        Build the Docker image using the docker python library. Optionally pushes the
        image if both `push`=`True` and `self.registry_url` is set.

        Args:
            - flow (prefect.Flow): Flow to be placed the image
            - push (bool): Whether or not to push to registry after build

        Returns:
            - tuple: `image_name`, `image_tag` (strings)
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
            if len(client.images(name=full_name)) == 0:
                raise SerializationError(
                    "Your flow failed to deserialize in the container; please ensure that all necessary files and dependencies have been included."
                )

            if push:
                self.push_image(full_name, image_tag)

                # Remove the image locally after being pushed
                client.remove_image(
                    image="{}:{}".format(full_name, image_tag), force=True
                )

            return image_name, image_tag

    def pull_image(self) -> None:
        """Pull the image specified so it can be built.

        In order for the docker python library to use a base image it must be pulled
        from either the main docker registry or a separate registry that must be set as
        `registry_url` on this class.
        """
        client = docker.APIClient(base_url="unix://var/run/docker.sock")

        output = client.pull(self.base_image, stream=True, decode=True)
        for line in output:
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")
        print("")

    def push_image(self, image_name: str, image_tag: str) -> None:
        """Push this environment to a registry

        Args:
            - image_name (str): Name for the image
            - image_tag (str): Tag for the image
        """
        client = docker.APIClient(base_url="unix://var/run/docker.sock")

        logging.info("Pushing image to the registry...")

        output = client.push(image_name, tag=image_tag, stream=True, decode=True)
        for line in output:
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")
        print("")

    def create_dockerfile(self, flow: "prefect.Flow", directory: str = None) -> None:
        """Creates a dockerfile to use as the container.

        In order for the docker python library to build a container it needs a
        Dockerfile that it can use to define the container. This function takes the
        image and python_dependencies then writes them to a file called Dockerfile.

        *Note*: if `files` are added to this container, they will be copied to this directory as well.

        Args:
            - flow (Flow): the flow that the container will run
            - directory (str, optional): A directory where the Dockerfile will be created,
                if no directory is specified is will be created in the current working directory
        """

        directory = directory or "./"

        with open(os.path.join(directory, "Dockerfile"), "w+") as dockerfile:

            # Generate RUN pip install commands for python dependencies
            pip_installs = ""
            if self.python_dependencies:
                for dependency in self.python_dependencies:
                    pip_installs += "RUN pip install {}\n".format(dependency)

            env_vars = ""
            if self.env_vars:
                white_space = " " * 20
                env_vars = "ENV " + " \ \n{}".format(white_space).join(
                    "{k}={v}".format(k=k, v=v) for k, v in self.env_vars.items()
                )

            copy_files = ""
            if self.files:
                for src, dest in self.files.items():
                    fname = os.path.basename(src)
                    full_fname = os.path.join(directory, fname)
                    if (
                        os.path.exists(full_fname)
                        and filecmp.cmp(src, full_fname) is False
                    ):
                        raise ValueError(
                            "File {fname} already exists in {directory}".format(
                                fname=full_fname, directory=directory
                            )
                        )
                    else:
                        shutil.copy2(src, full_fname)
                    copy_files += "COPY {fname} {dest}\n".format(fname=fname, dest=dest)

            # Create a LocalEnvironment to run the flow
            # the local environment will be placed in the container and run when the container
            # runs
            local_environment = LocalEnvironment().build(flow=flow)
            flow_path = os.path.join(directory, "flow_env.prefect")
            local_environment.to_file(flow_path)

            # write a healthcheck script into the image
            healthcheck = textwrap.dedent(
                """\
            print('Beginning health check...')
            from prefect.utilities.environments import from_file

            local_env = from_file('/root/.prefect/flow_env.prefect')
            flow = local_env.deserialize_flow_from_bytes(local_env.serialized_flow)
            print('Healthcheck: OK')
            """
            )

            with open(os.path.join(directory, "healthcheck.py"), "w") as health_file:
                health_file.write(healthcheck)

            file_contents = textwrap.dedent(
                """\
                FROM {base_image}

                RUN apt-get -qq -y update && apt-get -qq -y install --no-install-recommends --no-install-suggests git

                RUN pip install pip --upgrade
                RUN pip install wheel
                {pip_installs}

                RUN mkdir /root/.prefect/
                COPY flow_env.prefect /root/.prefect/flow_env.prefect
                COPY healthcheck.py /root/.prefect/healthcheck.py
                {copy_files}

                ENV PREFECT_ENVIRONMENT_FILE="/root/.prefect/flow_env.prefect"
                ENV PREFECT__USER_CONFIG_PATH="/root/.prefect/config.toml"
                {env_vars}

                RUN pip install prefect

                RUN python /root/.prefect/healthcheck.py
                """.format(
                    base_image=self.base_image,
                    pip_installs=pip_installs,
                    copy_files=copy_files,
                    env_vars=env_vars,
                    access_token=os.getenv("PERSONAL_ACCESS_TOKEN"),
                )
            )

            dockerfile.write(file_contents)
