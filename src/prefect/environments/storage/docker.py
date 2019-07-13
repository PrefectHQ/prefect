import filecmp
import json
import logging
import os
import shutil
import sys
import tempfile
import textwrap
import uuid
from typing import Any, Callable, Dict, Iterable, List

import cloudpickle
import docker
from slugify import slugify

import prefect
from prefect.environments.storage import Storage
from prefect.utilities.exceptions import SerializationError


class Docker(Storage):
    """
    Docker storage provides a mechanism for storing Prefect flows in Docker images
    and optionally pushing them to a registry.

    A user specifies a `base_image` and other optional dependencies (e.g., `python_dependencies`)
    and `build()` will create a temporary Dockerfile that is used to build the image.

    Note that the `base_image` must be capable of `pip` installing.

    Args:
        - registry_url (str, optional): URL of a registry to push the image to; image will not be pushed if not provided
        - base_image (str, optional): the base image for this environment (e.g. `python:3.6`), defaults to `python:3.6`
        - python_dependencies (List[str], optional): list of pip installable dependencies for the image
        - image_name (str, optional): name of the image to use when building, populated with a UUID after build
        - image_tag (str, optional): tag of the image to use when building, populated with a UUID after build
        - env_vars (dict, optional): a dictionary of environment variables to use when building
        - files (dict, optional): a dictionary of files to copy into the image when building
        - base_url: (str, optional): a URL of a Docker daemon to use when for Docker related functionality
        - prefect_version (str, optional): an optional branch, tag, or commit specifying the version of prefect
            you want installed into the container; defaults to the version you are currently using or `"master"` if your version is ahead of
            the latest tag
        - local_image(bool, optional): an optional flag whether or not to use a local docker image, if True then a pull will not be attempted
    """

    def __init__(
        self,
        registry_url: str = None,
        base_image: str = None,
        python_dependencies: List[str] = None,
        image_name: str = None,
        image_tag: str = None,
        env_vars: dict = None,
        files: dict = None,
        base_url: str = "unix://var/run/docker.sock",
        prefect_version: str = None,
        local_image: bool = False,
    ) -> None:
        self.registry_url = registry_url

        if base_image is None:
            python_version = "{}.{}".format(
                sys.version_info.major, sys.version_info.minor
            )
            self.base_image = "python:{}".format(python_version)
        else:
            self.base_image = base_image

        self.image_name = image_name
        self.image_tag = image_tag
        self.python_dependencies = python_dependencies or []
        self.env_vars = env_vars or {}
        self.files = files or {}
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "prefect.core.flow.Flow"]
        self.base_url = base_url
        self.local_image = local_image

        version = prefect.__version__.split("+")
        if prefect_version is None:
            self.prefect_version = "master" if len(version) > 1 else version[0]
        else:
            self.prefect_version = prefect_version

        not_absolute = [
            file_path for file_path in self.files if not os.path.isabs(file_path)
        ]
        if not_absolute:
            raise ValueError(
                "Provided paths {} are not absolute file paths, please provide absolute paths only.".format(
                    ", ".join(not_absolute)
                )
            )

    def get_env_runner(self, flow_location: str) -> Callable[[Dict[str, str]], None]:
        """
        Given a flow_location within this Storage object, returns something with a
        `run()` method which accepts the standard runner kwargs and can run the flow.

        Args:
            - flow_location (str): the location of a flow within this Storage

        Returns:
            - a runner interface (something with a `run()` method for running the flow)
        """

        def runner(env: dict) -> None:
            """
            Given a dictionary of environment variables, calls `flow.run()` with these
            environment variables set.
            """
            image = "{}:{}".format(self.image_name, self.image_tag)
            client = docker.APIClient(base_url=self.base_url, version="auto")
            container = client.create_container(image, command="tail -f /dev/null")
            client.start(container=container.get("Id"))
            python_script = "import cloudpickle; f = open('{}', 'rb'); flow = cloudpickle.load(f); f.close(); flow.run()".format(
                flow_location
            )
            try:
                ee = client.exec_create(
                    container.get("Id"),
                    'python -c "{}"'.format(python_script),
                    environment=env,
                )
                output = client.exec_start(exec_id=ee, stream=True)
                for item in output:
                    for line in item.decode("utf-8").split("\n"):
                        if line:
                            print(line)
            finally:
                client.stop(container=container.get("Id"))

        return runner

    def add_flow(self, flow: "prefect.core.flow.Flow") -> str:
        """
        Method for adding a new flow to this Storage object.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the location of the newly added flow in this Storage object
        """
        if flow.name in self:
            raise ValueError(
                'Name conflict: Flow with the name "{}" is already present in this storage.'.format(
                    flow.name
                )
            )
        flow_path = "/root/.prefect/{}.prefect".format(slugify(flow.name))
        self.flows[flow.name] = flow_path
        self._flows[flow.name] = flow  # needed prior to build
        return flow_path

    @property
    def name(self) -> str:
        """
        Full name of the Docker image.
        """
        if None in [self.registry_url, self.image_name, self.image_tag]:
            raise ValueError("Docker storage is missing required fields")

        return "{}:{}".format(
            os.path.join(self.registry_url, self.image_name),  # type: ignore
            self.image_tag,  # type: ignore
        )

    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is contained within this storage.
        """
        if not isinstance(obj, str):
            return False
        return obj in self.flows

    def build(self, push: bool = True) -> "Storage":
        """
        Build the Docker storage object.

        Args:
            - push (bool, optional): Whether or not to push the built Docker image, this
                requires the `registry_url` to be set

        Returns:
            - Docker: a new Docker storage object that contains information about how and
                where the flow is stored. Image name and tag are generated during the
                build process.

        Raises:
            - InterruptedError: if either pushing or pulling the image fails
        """
        image_name, image_tag = self.build_image(push=push)
        self.image_name = image_name
        self.image_tag = image_tag

        return self

    def build_image(self, push: bool = True) -> tuple:
        """
        Build a Docker image using the docker python library.

        Args:
            - push (bool, optional): Whether or not to push the built Docker image, this
                requires the `registry_url` to be set

        Returns:
            - tuple: generated UUID strings `image_name`, `image_tag`

        Raises:
            - InterruptedError: if either pushing or pulling the image fails
        """
        image_name = self.image_name or str(uuid.uuid4())
        image_tag = self.image_tag or str(uuid.uuid4())

        # Make temporary directory to hold serialized flow, healthcheck script, and dockerfile
        with tempfile.TemporaryDirectory() as tempdir:

            # Build the dockerfile
            if self.base_image and not self.local_image:
                self.pull_image()

            self.create_dockerfile_object(directory=tempdir)
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

    def create_dockerfile_object(self, directory: str = None) -> None:
        """
        Writes a dockerfile to the provided directory using the specified
        arguments on this Docker storage object.

        In order for the docker python library to build a container it needs a
        Dockerfile that it can use to define the container. This function takes the
        specified arguments then writes them to a temporary file called Dockerfile.

        *Note*: if `files` are added to this container, they will be copied to this directory as well.

        Args:
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

            # Write all flows to file and load into the image
            copy_flows = ""
            for flow_name, flow_location in self.flows.items():
                clean_name = slugify(flow_name)
                flow_path = os.path.join(directory, "{}.flow".format(clean_name))
                with open(flow_path, "wb") as f:
                    cloudpickle.dump(self._flows[flow_name], f)
                copy_flows += "COPY {source} {dest}\n".format(
                    source="{}.flow".format(clean_name), dest=flow_location
                )

            # Write a healthcheck script into the image
            healthcheck = textwrap.dedent(
                """\
            print('Beginning health check...')
            import cloudpickle
            import sys
            import warnings

            for flow_file in [{flow_file_paths}]:
                with open(flow_file, 'rb') as f:
                    flow = cloudpickle.load(f)

            if sys.version_info.minor < {python_version}[1] or sys.version_info.minor > {python_version}[1]:
                msg = "Your Docker container is using python version {{sys_ver}}, but your Flow was serialized using {{user_ver}}; this could lead to unexpected errors in deployment.".format(sys_ver=(sys.version_info.major, sys.version_info.minor), user_ver={python_version})
                warnings.warn(msg)

            print('Healthcheck: OK')
            """.format(
                    flow_file_paths=", ".join(
                        ["'{}'".format(k) for k in self.flows.values()]
                    ),
                    python_version=(sys.version_info.major, sys.version_info.minor),
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
                {copy_flows}
                COPY healthcheck.py /root/.prefect/healthcheck.py
                {copy_files}

                ENV PREFECT__USER_CONFIG_PATH="/root/.prefect/config.toml"
                {env_vars}

                RUN pip install git+https://github.com/PrefectHQ/prefect.git@{version}#egg=prefect[kubernetes]
                # RUN pip install prefect

                RUN python /root/.prefect/healthcheck.py
                """.format(
                    base_image=self.base_image,
                    pip_installs=pip_installs,
                    copy_flows=copy_flows,
                    copy_files=copy_files,
                    env_vars=env_vars,
                    version=self.prefect_version,
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

        Raises:
            - InterruptedError: if either pulling the image fails
        """
        client = docker.APIClient(base_url=self.base_url, version="auto")

        output = client.pull(self.base_image, stream=True, decode=True)
        for line in output:
            if line.get("error"):
                raise InterruptedError(line.get("error"))
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")
        print("")

    def push_image(self, image_name: str, image_tag: str) -> None:
        """Push this environment to a registry

        Args:
            - image_name (str): Name for the image
            - image_tag (str): Tag for the image

        Raises:
            - InterruptedError: if either pushing the image fails
        """
        client = docker.APIClient(base_url=self.base_url, version="auto")

        logging.info("Pushing image to the registry...")

        output = client.push(image_name, tag=image_tag, stream=True, decode=True)
        for line in output:
            if line.get("error"):
                raise InterruptedError(line.get("error"))
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
