import filecmp
import json
import logging
import os
import shutil
import tempfile
import textwrap
import uuid
from typing import Iterable, List

import docker

import prefect
from prefect.environments.storage import Storage
from prefect.utilities.exceptions import SerializationError


class Docker(Storage):
    """"""

    def __init__(
        self,
        registry_url: str = None,
        dockerfile: str = None,
        base_image: str = None,
        python_dependencies: List[str] = None,
        image_name: str = None,
        image_tag: str = None,
        env_vars: dict = None,
        files: dict = None,
        flow_file_path: str = "/root/.prefect/flow_env.prefect",
        base_url: str = "unix://var/run/docker.sock",
    ) -> None:
        self.registry_url = registry_url
        self.dockerfile = dockerfile
        self.base_image = base_image
        self.image_name = image_name
        self.image_tag = image_tag
        self.python_dependencies = python_dependencies or []
        self.env_vars = env_vars or {}
        self.files = files or {}
        self.flow_file_path = flow_file_path
        self.base_url = base_url

        not_absolute = [
            file_path for file_path in self.files if not os.path.isabs(file_path)
        ]
        if not_absolute:
            raise ValueError(
                "Provided paths {} are not absolute file paths, please provide absolute paths only.".format(
                    ", ".join(not_absolute)
                )
            )

    def build(self, flow: "prefect.Flow", push: bool = True) -> "Storage":
        """"""
        if bool(self.base_image) != bool(self.dockerfile):
            # TODO: Default to prefect base image
            raise ValueError(
                "You must provide either a base image or a dockerfile, but not both."
            )

        image_name, image_tag = self.build_image(flow=flow, push=push)

        return Docker(
            registry_url=self.registry_url, image_name=image_name, image_tag=image_tag
        )

    def build_image(self, flow: "prefect.Flow", push: bool = True) -> tuple:
        """"""
        image_name = str(uuid.uuid4())
        image_tag = str(uuid.uuid4())

        # Make temporary directory to hold serialized flow, healthcheck script, and dockerfile
        with tempfile.TemporaryDirectory() as tempdir:

            # Build the dockerfile
            if self.base_image:
                self.pull_image()
                self.create_dockerfile_object_from_base_image(
                    flow=flow, directory=tempdir
                )
            else:
                self.create_dockerfile_object_from_dockerfile(
                    flow=flow, directory=tempdir
                )

            client = docker.APIClient(base_url=self.base_url, version="auto")

            # Verify that a registry url has been provided for images that should be pushed
            if self.registry_url:
                full_name = os.path.join(self.registry_url, image_name)
            elif push is True:
                raise ValueError(
                    "This environment has no `registry_url`, and cannot be pushed."
                )
            else:
                full_name = image_name

            # Use the docker client to build the image
            logging.info("Building the flow's Docker storage...")
            output = client.build(
                path=tempdir, tag="{}:{}".format(full_name, image_tag), forcerm=True
            )
            self._parse_generator_output(output)

            if len(client.images(name=full_name)) == 0:
                raise SerializationError(
                    "Your flow failed to deserialize in the container; please ensure that all necessary files and dependencies have been included."
                )

            # Push the image if requested
            if push:
                self.push_image(full_name, image_tag)

                # Remove the image locally after being pushed
                client.remove_image(
                    image="{}:{}".format(full_name, image_tag), force=True
                )

        return image_name, image_tag

    ########################
    # Dockerfile Creation
    ########################

    def create_dockerfile_object_from_base_image(
        self, flow: "prefect.Flow", directory: str = None
    ) -> None:
        """"""
        directory = directory or "./"

        with open(os.path.join(directory, "Dockerfile"), "w+") as dockerfile:

            # Generate RUN pip install commands for python dependencies
            pip_installs = ""
            if self.python_dependencies:
                for dependency in self.python_dependencies:
                    pip_installs += "RUN pip install {}\n".format(dependency)

            # Generate ENV variables to load into the image
            env_vars = ""
            if self.env_vars:
                white_space = " " * 20
                env_vars = "ENV " + " \ \n{}".format(white_space).join(
                    "{k}={v}".format(k=k, v=v) for k, v in self.env_vars.items()
                )

            # Copy user specified files into the image
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

            # Write the flow to a file and load into the image
            flow_path = os.path.join(directory, "flow_env.prefect")
            with open(flow_path, "w") as f:
                json.dump(flow.serialize(), f)

            # Write a healthcheck script into the image
            healthcheck = textwrap.dedent(
                """\
            print('Beginning health check...')
            from prefect.utilities.environments import from_file

            local_env = from_file('{flow_file_path}')
            flow = local_env.deserialize_flow_from_bytes(local_env.serialized_flow)
            print('Healthcheck: OK')
            """.format(
                    flow_file_path=self.flow_file_path
                )
            )

            with open(os.path.join(directory, "healthcheck.py"), "w") as health_file:
                health_file.write(healthcheck)

            file_contents = textwrap.dedent(
                """\
                FROM {base_image}

                RUN pip install pip --upgrade
                RUN pip install wheel
                {pip_installs}

                RUN mkdir /root/.prefect/
                COPY flow_env.prefect {flow_file_path}
                COPY healthcheck.py /root/.prefect/healthcheck.py
                {copy_files}

                ENV PREFECT_ENVIRONMENT_FILE="{flow_file_path}"
                ENV PREFECT__USER_CONFIG_PATH="/root/.prefect/config.toml"
                {env_vars}

                RUN pip install prefect

                RUN python /root/.prefect/healthcheck.py
                """.format(
                    base_image=self.base_image,
                    pip_installs=pip_installs,
                    copy_files=copy_files,
                    flow_file_path=self.flow_file_path,
                    env_vars=env_vars,
                )
            )

            dockerfile.write(file_contents)

    def create_dockerfile_object_from_dockerfile(
        self, flow: "prefect.Flow", directory: str = None
    ) -> None:
        """"""
        directory = directory or "./"

        with open(os.path.join(directory, "Dockerfile"), "w+") as dockerfile:

            # Write the flow to a file and load into the image
            flow_path = os.path.join(directory, "flow_env.prefect")
            with open(flow_path, "w") as f:
                json.dump(flow.serialize(), f)

            # Write a healthcheck script into the image
            healthcheck = textwrap.dedent(
                """\
            print('Beginning health check...')
            from prefect.utilities.environments import from_file

            local_env = from_file('{flow_file_path}')
            flow = local_env.deserialize_flow_from_bytes(local_env.serialized_flow)
            print('Healthcheck: OK')
            """.format(
                    flow_file_path=self.flow_file_path
                )
            )

            with open(os.path.join(directory, "healthcheck.py"), "w") as health_file:
                health_file.write(healthcheck)

            file_contents = textwrap.dedent(
                """\
                {dockerfile}

                RUN mkdir /root/.prefect/
                COPY flow_env.prefect {flow_file_path}
                COPY healthcheck.py /root/.prefect/healthcheck.py

                ENV PREFECT_ENVIRONMENT_FILE="{flow_file_path}"
                ENV PREFECT__USER_CONFIG_PATH="/root/.prefect/config.toml"

                RUN pip install prefect

                RUN python /root/.prefect/healthcheck.py
                """.format(
                    dockerfile=self.dockerfile, flow_file_path=self.flow_file_path
                )
            )

            dockerfile.write(file_contents)

    ########################
    # Docker Utilities
    ########################

    def pull_image(self) -> None:
        """Pull the image specified so it can be built.

        In order for the docker python library to use a base image it must be pulled
        from either the main docker registry or a separate registry that must be set as
        `registry_url` on this class.
        """
        client = docker.APIClient(base_url=self.base_url, version="auto")

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
        client = docker.APIClient(base_url=self.base_url, version="auto")

        logging.info("Pushing image to the registry...")

        output = client.push(image_name, tag=image_tag, stream=True, decode=True)
        for line in output:
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")
        print("")

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
