import filecmp
import json
import os
import copy
import re
import shutil
import sys
import tempfile
import textwrap
import uuid
import warnings
from pathlib import PurePosixPath, Path
from typing import TYPE_CHECKING, Any, Iterable, List, Union

import pendulum
from slugify import slugify

import prefect
from prefect.storage import Storage
from prefect.utilities.storage import (
    extract_flow_from_file,
    flow_from_bytes_pickle,
    flow_to_bytes_pickle,
)

if TYPE_CHECKING:
    import docker


def multiline_indent(string: str, spaces: int) -> str:
    """
    Utility to indent all but the first line in a string to the specified level,
    especially useful in textwrap.dedent calls where multiline strings are formatted in
    """
    return string.replace("\n", "\n" + " " * spaces)


class Docker(Storage):
    """
    Docker storage provides a mechanism for storing Prefect flows in Docker
    images and optionally pushing them to a registry.

    A user specifies a `registry_url`, `base_image` and other optional
    dependencies (e.g., `python_dependencies`) and `build()` will create a
    temporary Dockerfile that is used to build the image.

    Note that the `base_image` must be capable of `pip` installing.  Note that
    registry behavior with respect to image names can differ between providers -
    for example, Google's GCR registry allows for registry URLs of the form
    `gcr.io/my-registry/subdir/my-image-name` whereas DockerHub requires the
    registry URL to be separate from the image name.

    Custom modules can be packaged up during build by attaching the files and
    setting the `PYTHONPATH` to the location of those files. Otherwise the
    modules can be set independently when using a custom base image prior to the
    build here.

    ```python
    Docker(
        files={
            # absolute path source -> destination in image
            "/Users/me/code/mod1.py": "/modules/mod1.py",
            "/Users/me/code/mod2.py": "/modules/mod2.py",
        },
        env_vars={
            # append modules directory to PYTHONPATH
            "PYTHONPATH": "$PYTHONPATH:modules/"
        },
    )
    ```

    Args:
        - registry_url (str, optional): URL of a registry to push the image to;
            image will not be pushed if not provided
        - base_image (str, optional): the base image for this when building this
            image (e.g. `python:3.7`), defaults to the `prefecthq/prefect` image
            matching your python version and prefect core library version used
            at runtime.
        - dockerfile (str, optional): a path to a Dockerfile to use in building
            this storage; note that, if provided, your present working directory
            will be used as the build context
        - python_dependencies (List[str], optional): list of pip installable
            dependencies for the image
        - image_name (str, optional): name of the image to use when building,
            populated with a UUID after build
        - image_tag (str, optional): tag of the image to use when building,
            populated with a UUID after build
        - env_vars (dict, optional): a dictionary of environment variables to
            use when building
        - files (dict, optional): a dictionary of files or directories to copy into
            the image when building. Takes the format of `{'src': 'dest'}`
        - dockerignore (str, optional): an optional Path to a `dockerignore` file.
            when used with the `files` argument, the specified `dockerignore` will be
            included in the build context
        - prefect_version (str, optional): an optional branch, tag, or commit
            specifying the version of prefect you want installed into the container;
            defaults to the version you are currently using or `"master"` if your
            version is ahead of the latest tag
        - local_image (bool, optional): an optional flag whether or not to use a
            local docker image, if True then a pull will not be attempted
        - ignore_healthchecks (bool, optional): if True, the Docker healthchecks
            are not added to the Dockerfile. If False (default), healthchecks
            are included.
        - base_url (str, optional): a URL of a Docker daemon to use when for
            Docker related functionality.  Defaults to DOCKER_HOST env var if not set
        - tls_config (Union[bool, docker.tls.TLSConfig], optional): a TLS configuration to pass
            to the Docker client.
            [Documentation](https://docker-py.readthedocs.io/en/stable/tls.html#docker.tls.TLSConfig)
        - build_kwargs (dict, optional): Additional keyword arguments to pass to Docker's build
            step. [Documentation](
                https://docker-py.readthedocs.io/en/stable/api.html#docker.api.build.BuildApiMixin.build
            )
        - prefect_directory (str, optional): Path to the directory where prefect configuration/flows
             should be stored inside the Docker image. Defaults to `/opt/prefect`.
        - path (str, optional): a direct path to the location of the flow file in the Docker image
            if `stored_as_script=True`.
        - stored_as_script (bool, optional): boolean for specifying if the flow has been stored
            as a `.py` file. Defaults to `False`
        - extra_dockerfile_commands (list[str], optional): list of Docker build commands
            which are injected at the end of generated DockerFile (before the health checks).
            Defaults to `None`
        - **kwargs (Any, optional): any additional `Storage` initialization options

    Raises:
        - ValueError: if both `base_image` and `dockerfile` are provided

    """

    def __init__(
        self,
        registry_url: str = None,
        base_image: str = None,
        dockerfile: str = None,
        dockerignore: str = None,
        python_dependencies: List[str] = None,
        image_name: str = None,
        image_tag: str = None,
        env_vars: dict = None,
        files: dict = None,
        prefect_version: str = None,
        local_image: bool = False,
        ignore_healthchecks: bool = False,
        base_url: str = None,
        tls_config: Union[bool, "docker.tls.TLSConfig"] = False,
        build_kwargs: dict = None,
        prefect_directory: str = "/opt/prefect",
        path: str = None,
        stored_as_script: bool = False,
        extra_dockerfile_commands: List[str] = None,
        **kwargs: Any,
    ) -> None:
        self.registry_url = registry_url
        if sys.platform == "win32":
            default_url = "npipe:////./pipe/docker_engine"
        else:
            default_url = "unix://var/run/docker.sock"
        self.image_name = image_name
        self.image_tag = image_tag
        self.python_dependencies = python_dependencies or []
        self.python_dependencies.append("wheel")

        self.prefect_directory = prefect_directory
        self.path = path

        self.env_vars = env_vars or {}
        self.env_vars.setdefault(
            "PREFECT__USER_CONFIG_PATH", "{}/config.toml".format(self.prefect_directory)
        )

        self.files = files or {}
        self.local_image = local_image
        self.installation_commands = []  # type: List[str]
        self.ignore_healthchecks = ignore_healthchecks

        self.base_url = base_url or os.environ.get("DOCKER_HOST", default_url)
        self.tls_config = tls_config
        self.build_kwargs = copy.copy(build_kwargs) or {}
        self.rm_build_kwarg = self.build_kwargs.pop("rm", True)
        self.extra_dockerfile_commands = extra_dockerfile_commands

        version = prefect.__version__.split("+")
        if prefect_version is None:
            self.prefect_version = (
                "master"
                # The release candidate is a special development version
                if len(version) > 1 and not version[0].endswith("rc0")
                else version[0]
            )
        else:
            self.prefect_version = prefect_version

        if base_image is None and dockerfile is None:
            python_version = "{}.{}".format(
                sys.version_info.major, sys.version_info.minor
            )
            if re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", self.prefect_version) is not None:
                self.base_image = "prefecthq/prefect:{}-python{}".format(
                    self.prefect_version, python_version
                )
            elif self.prefect_version.endswith("rc0"):
                # Development release candidate
                self.base_image = f"prefecthq/prefect:{self.prefect_version}"
            elif (
                re.match(r"^[0-9]+\.[0-9]+rc[0-9]+$", self.prefect_version) is not None
            ):
                # Actual release candidate
                self.base_image = "prefecthq/prefect:{}-python{}".format(
                    self.prefect_version, python_version
                )
            else:
                # create an image from python:*-slim directly
                self.base_image = "python:{}-slim".format(python_version)
                self.installation_commands.append(
                    "apt update && apt install -y gcc git make && rm -rf /var/lib/apt/lists/*"
                )
        elif base_image and dockerfile:
            raise ValueError(
                "Only one of `base_image` and `dockerfile` can be provided."
            )
        else:
            self.base_image = base_image  # type: ignore

        self.dockerfile = dockerfile
        self.dockerignore = dockerignore
        # we should always try to install prefect, unless it is already installed. We can't
        # determine this until image build time.
        self.installation_commands.append(
            f"pip show prefect || "
            f"pip install git+https://github.com/PrefectHQ/prefect.git"
            f"@{self.prefect_version}#egg=prefect[all_orchestration_extras]"
        )

        not_absolute = [
            file_path for file_path in self.files if not os.path.isabs(file_path)
        ]
        if not_absolute:
            raise ValueError(
                (
                    "Provided paths {} are not absolute file paths, please provide "
                    "absolute paths only."
                ).format(", ".join(not_absolute))
            )
        super().__init__(stored_as_script=stored_as_script, **kwargs)

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
        flow_path = self.path or "{}/flows/{}.prefect".format(
            self.prefect_directory, slugify(flow.name)
        )
        self.flows[flow.name] = flow_path
        self._flows[flow.name] = flow  # needed prior to build
        return flow_path

    def get_flow(self, flow_name: str) -> "prefect.core.flow.Flow":
        """
        Given a flow name within this Storage object, load and return the Flow.

        Args:
            - flow_name (str): the name of the flow to return.

        Returns:
            - Flow: the requested flow
        """
        if flow_name not in self.flows:
            raise ValueError("Flow is not contained in this Storage")
        flow_location = self.flows[flow_name]

        if self.stored_as_script:
            return extract_flow_from_file(file_path=flow_location, flow_name=flow_name)

        with open(flow_location, "rb") as f:
            return flow_from_bytes_pickle(f.read())

    @property
    def name(self) -> str:
        """
        Full name of the Docker image.
        """
        if None in [self.image_name, self.image_tag]:
            raise ValueError(
                "Docker storage is missing required fields image_name and image_tag"
            )

        return "{}:{}".format(
            PurePosixPath(self.registry_url or "", self.image_name),  # type: ignore
            self.image_tag,  # type: ignore
        )

    def build(self, push: bool = True) -> "Storage":
        """
        Build the Docker storage object.  If image name and tag are not set,
        they will be autogenerated.

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
        if len(self.flows) != 1:
            self.image_name = self.image_name or str(uuid.uuid4())
        else:
            self.image_name = self.image_name or slugify(list(self.flows.keys())[0])

        self.image_tag = self.image_tag or slugify(pendulum.now("utc").isoformat())
        self._build_image(push=push)
        return self

    def _build_image(self, push: bool = True) -> tuple:
        """
        Build a Docker image using the docker python library.

        Args:
            - push (bool, optional): Whether or not to push the built Docker image, this
                requires the `registry_url` to be set

        Returns:
            - tuple: generated UUID strings `image_name`, `image_tag`

        Raises:
            - ValueError: if the image fails to build
            - InterruptedError: if either pushing or pulling the image fails
        """
        assert isinstance(self.image_name, str), "Image name must be provided"
        assert isinstance(self.image_tag, str), "An image tag must be provided"

        # Make temporary directory to hold serialized flow, healthcheck script, and dockerfile
        # note that if the user provides a custom dockerfile, we create the temporary directory
        # within the current working directory to preserve their build context
        with tempfile.TemporaryDirectory(
            dir="." if self.dockerfile else None
        ) as tempdir:
            # Build the dockerfile
            if self.base_image and not self.local_image:
                self.pull_image()

            dockerfile_path = self.create_dockerfile_object(directory=tempdir)
            client = self._get_client()

            # Verify that a registry url has been provided for images that should be
            # pushed
            if self.registry_url:
                full_name = str(PurePosixPath(self.registry_url, self.image_name))
            elif push is True:
                warnings.warn(
                    "This Docker storage object has no `registry_url`, and "
                    "will not be pushed.",
                    UserWarning,
                    stacklevel=2,
                )
                full_name = self.image_name
            else:
                full_name = self.image_name

            # Use the docker client to build the image
            self.logger.info("Building the flow's Docker storage...")

            if sys.platform == "win32":
                # problem with docker and relative paths only on windows
                dockerfile_path = os.path.abspath(dockerfile_path)

            output = client.build(
                path="." if self.dockerfile else tempdir,
                dockerfile=dockerfile_path,
                tag="{}:{}".format(full_name, self.image_tag),
                rm=self.rm_build_kwarg,
                **self.build_kwargs,
            )
            self._parse_generator_output(output)

            if len(client.images(name="{}:{}".format(full_name, self.image_tag))) == 0:
                raise ValueError(
                    "Your docker image failed to build!  Your flow might have "
                    "failed one of its deployment health checks - please ensure "
                    "that all necessary files and dependencies have been included."
                )

            # Push the image if requested
            if push and self.registry_url:
                self.push_image(full_name, self.image_tag)

                # Remove the image locally after being pushed
                client.remove_image(
                    image="{}:{}".format(full_name, self.image_tag), force=True
                )

        return self.image_name, self.image_tag

    ########################
    # Dockerfile Creation
    ########################

    def create_dockerfile_object(self, directory: str) -> str:
        """
        Writes a dockerfile to the provided directory using the specified
        arguments on this Docker storage object.

        In order for the docker python library to build a container it needs a
        Dockerfile that it can use to define the container. This function takes the
        specified arguments then writes them to a temporary file called Dockerfile.

        *Note*: if `files` are added to this container, they will be copied to this
        directory as well.

        Args:
            - directory (str): A directory where the Dockerfile will be created

        Returns:
            - str: the absolute file path to the Dockerfile
        """
        # Either load the base commands from the specified dockerfile or define a FROM
        if self.dockerfile:
            with open(self.dockerfile, "r") as contents:
                base_commands = contents.read()
        else:
            base_commands = "FROM {base_image}".format(base_image=self.base_image)

        # Generate ENV variables to load into the image
        env_vars = ""
        if self.env_vars:
            # Format with repr to get proper quoting
            formatted_vars = [f"{k}={v!r}" for k, v in self.env_vars.items()]
            env_vars = "ENV " + " \\\n    ".join(formatted_vars)

        # Generate single pip install command for python dependencies
        pip_installs = "RUN pip install "
        if self.python_dependencies:
            for dependency in self.python_dependencies:
                pip_installs += "'{}' ".format(dependency)

        # Write all install-time commands that should be run in the image
        installation_commands = ""
        for cmd in self.installation_commands:
            installation_commands += "RUN {}\n".format(cmd)

        # Copy user specified files into the image
        copy_files = ""
        if self.files:
            # copy dockerignore if provided
            if self.dockerignore:
                shutil.copyfile(
                    src=Path(self.dockerignore).expanduser().resolve(),
                    dst=Path(directory) / ".dockerignore",
                )
            for src, dest in self.files.items():
                fname = os.path.basename(src)
                full_fname = os.path.join(directory, fname)
                if os.path.exists(full_fname) and filecmp.cmp(src, full_fname) is False:
                    raise ValueError(
                        "File {fname} already exists in {directory}".format(
                            fname=full_fname, directory=directory
                        )
                    )
                else:
                    if os.path.isdir(src):
                        shutil.copytree(
                            src=src, dst=full_fname, symlinks=False, ignore=None
                        )
                    else:
                        shutil.copy2(src=src, dst=full_fname)
                copy_files += "COPY {fname} {dest}\n".format(
                    fname=full_fname.replace("\\", "/") if self.dockerfile else fname,
                    dest=dest,
                )

        # Write all flows to file and load into the image
        copy_flows = ""
        if not self.stored_as_script:
            for flow_name, flow_location in self.flows.items():
                clean_name = slugify(flow_name)
                flow_path = os.path.join(directory, "{}.flow".format(clean_name))
                with open(flow_path, "wb") as f:
                    f.write(flow_to_bytes_pickle(self._flows[flow_name]))
                copy_flows += "COPY {source} {dest}\n".format(
                    source=(
                        flow_path.replace("\\", "/")
                        if self.dockerfile
                        else "{}.flow".format(clean_name)
                    ),
                    dest=flow_location,
                )
        else:
            if not self.path:
                raise ValueError(
                    "A `path` must be provided to show where flow `.py` file is stored in the image."
                )

        # Write final extra user commands that should be run in the image
        final_commands = (
            ""
            if self.extra_dockerfile_commands is None
            else "\n".join(self.extra_dockerfile_commands)
        )

        # Write a healthcheck script into the image
        with open(
            os.path.join(os.path.dirname(__file__), "_healthcheck.py"), "r"
        ) as healthscript:
            healthcheck = healthscript.read()

        healthcheck_loc = os.path.join(directory, "healthcheck.py")
        with open(healthcheck_loc, "w") as health_file:
            health_file.write(healthcheck)

        # Escape the healthcheck location
        healthcheck_loc = (
            healthcheck_loc.replace("\\", "/") if self.dockerfile else "healthcheck.py"
        )

        # Generate the command to run the healthcheck
        healthcheck_run = ""
        if not self.ignore_healthchecks:
            flow_file_paths = ", ".join(['"{}"'.format(k) for k in self.flows.values()])
            python_version = (sys.version_info.major, sys.version_info.minor)
            healthcheck_run = (
                f"RUN python {self.prefect_directory}/healthcheck.py "
                f"'[{flow_file_paths}]' '{python_version}'"
            )

        file_contents = textwrap.dedent(
            f"""
            {multiline_indent(base_commands, 12)}
            {multiline_indent(env_vars, 12)}

            RUN pip install pip --upgrade
            {multiline_indent(installation_commands, 12)}
            {pip_installs}

            RUN mkdir -p {self.prefect_directory}/
            {multiline_indent(copy_flows, 12)}
            COPY {healthcheck_loc} {self.prefect_directory}/healthcheck.py
            {multiline_indent(copy_files, 12)}

            {multiline_indent(final_commands, 12)}
            {healthcheck_run}
            """
        )

        dockerfile_path = os.path.join(directory, "Dockerfile")
        with open(dockerfile_path, "w+") as dockerfile:
            dockerfile.write(file_contents)
        return dockerfile_path

    ########################
    # Docker Utilities
    ########################

    def _get_client(self) -> "docker.APIClient":
        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        return docker.APIClient(
            base_url=self.base_url, version="auto", tls=self.tls_config
        )

    def pull_image(self) -> None:
        """Pull the image specified so it can be built.

        In order for the docker python library to use a base image it must be pulled
        from either the main docker registry or a separate registry that must be set as
        `registry_url` on this class.

        Raises:
            - InterruptedError: if either pulling the image fails
        """
        client = self._get_client()

        output = client.pull(self.base_image, stream=True, decode=True)
        for line in output:
            if line.get("error"):
                raise InterruptedError(line.get("error"))
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")
        print("")

    def push_image(self, image_name: str, image_tag: str) -> None:
        """Push this image to a registry

        Args:
            - image_name (str): Name for the image
            - image_tag (str): Tag for the image

        Raises:
            - InterruptedError: if either pushing the image fails
        """
        client = self._get_client()

        self.logger.info("Pushing image to the registry...")

        output = client.push(image_name, tag=image_tag, stream=True, decode=True)
        for line in output:
            if line.get("error"):
                raise InterruptedError(line.get("error"))
            if line.get("progress"):
                print(line.get("status"), line.get("progress"), end="\r")
        print("")

    @staticmethod
    def _parse_generator_output(generator: Iterable) -> None:
        """
        Parses and writes a Docker command's output to stdout
        """
        for item in generator:
            item = item.decode("utf-8")
            for line in item.split("\n"):
                if not line:
                    continue
                parsed = json.loads(line)
                if not isinstance(parsed, dict):
                    continue
                # Parse several possible schemas
                output = (
                    parsed.get("stream")
                    or parsed.get("message")
                    or parsed.get("errorDetail", {}).get("message")
                    or ""
                ).strip("\n")
                if output:
                    print(output)
