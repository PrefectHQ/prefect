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

import prefect
from prefect.environments import Environment
from prefect.environments import LocalEnvironment


class DockerEnvironment(Environment):
    """"""

    def __init__(
        self,
        base_image: str,
        registry_url: str = None,
        python_dependencies: list = None,
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
        Build the Docker container. Returns a Container Environment with the appropriate
        image_name and image_tag set.

        Args:
            - flow (prefect.Flow): Flow to be placed in container
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
        """"""
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

            return image_name, image_tag

    def pull_image(self) -> None:
        """Pull the image specified so it can be built.

        In order for the docker python library to use a base image it must be pulled
        from either the main docker registry or a separate registry that must be set in
        the environment variables.
        """
        client = docker.APIClient(base_url="unix://var/run/docker.sock")

        output = client.pull(self.base_image, stream=True, decode=True)
        for line in output:
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")

    def push_image(self, image_name: str, image_tag: str) -> None:
        """Push this environment to a registry

        Args:
            - image_name (str): Name for the image
            - image_tag (str): Tag for the image

        Returns:
            - None
        """
        client = docker.APIClient(base_url="unix://var/run/docker.sock")

        logging.info("Pushing image to the registry...")

        output = client.push(image_name, tag=image_tag, stream=True, decode=True)
        for line in output:
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")

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

        Returns:
            - None
        """

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

            # Due to prefect being a private repo it currently will require a
            # personal access token. Once pip installable this will change and there won't
            # be a need for the personal access token or git anymore.
            # *Note*: this currently prevents alpine images from being used

            file_contents = textwrap.dedent(
                """\
                FROM {base_image}

                RUN apt-get -qq -y update && apt-get -qq -y install --no-install-recommends --no-install-suggests git

                RUN pip install pip --upgrade
                RUN pip install wheel
                {pip_installs}

                RUN mkdir /root/.prefect/
                COPY flow_env.prefect /root/.prefect/flow_env.prefect
                {copy_files}

                ENV PREFECT_ENVIRONMENT_FILE="/root/.prefect/flow_env.prefect"
                ENV PREFECT__USER_CONFIG_PATH="/root/.prefect/config.toml"
                {env_vars}

                RUN git clone https://{access_token}@github.com/PrefectHQ/prefect.git
                RUN pip install ./prefect
                """.format(
                    base_image=self.base_image,
                    pip_installs=pip_installs,
                    copy_files=copy_files,
                    env_vars=env_vars,
                    access_token=os.getenv("PERSONAL_ACCESS_TOKEN"),
                )
            )

            dockerfile.write(file_contents)
