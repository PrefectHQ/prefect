import os
import shutil
import tempfile

import pytest

import prefect
from prefect import Flow, Parameter, Task
from prefect.environments import DockerEnvironment

#################################
##### Docker Environment Tests
#################################


class TestDockerEnvironment:
    def test_create_docker_environment(self):
        docker = DockerEnvironment(base_image=None, registry_url=None)
        assert docker

    @pytest.mark.skip("Circle will need to handle container building")
    def test_build_image_process(self):

        docker = DockerEnvironment(
            base_image="python:3.6", image_tag="tag", registry_url=""
        )
        image = docker.build(Flow(name="test"))
        assert image

    def test_basic_create_dockerfile(self):
        docker = DockerEnvironment(base_image="python:3.6", registry_url="")
        with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
            docker.create_dockerfile(Flow(name="test"), directory=tmp)
            with open(os.path.join(tmp, "Dockerfile"), "r") as f:
                dockerfile = f.read()

        assert "FROM python:3.6" in dockerfile
        assert " FROM python:3.6" not in dockerfile
        assert "RUN pip install prefect" in dockerfile
        assert "RUN mkdir /root/.prefect/" in dockerfile

    def test_create_dockerfile_with_environment_variables(self):
        docker = DockerEnvironment(
            base_image="python:3.6",
            registry_url="",
            env_vars=dict(X=2, Y='"/a/quoted/string/path"'),
        )
        with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
            docker.create_dockerfile(Flow(name="test"), directory=tmp)
            with open(os.path.join(tmp, "Dockerfile"), "r") as f:
                dockerfile = f.read()

        var_orders = [
            'X=2 \\ \n    Y="/a/quoted/string/path"',
            'Y="/a/quoted/string/path" \\ \n    X=2',
        ]
        assert any(["ENV {}".format(v) in dockerfile for v in var_orders])

    def test_create_dockerfile_with_copy_files(self):
        with tempfile.NamedTemporaryFile() as t1, tempfile.NamedTemporaryFile() as t2:
            docker = DockerEnvironment(
                base_image="python:3.6",
                registry_url="",
                files={t1.name: "/root/dockerconfig", t2.name: "./.secret_file"},
            )

            base1, base2 = os.path.basename(t1.name), os.path.basename(t2.name)

            with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
                docker.create_dockerfile(Flow(name="test"), directory=tmp)

                ## ensure create_dockerfile copied the files over
                assert os.path.exists(os.path.join(tmp, base1))
                assert os.path.exists(os.path.join(tmp, base2))

                with open(os.path.join(tmp, "Dockerfile"), "r") as f:
                    dockerfile = f.read()

        assert "COPY {} /root/dockerconfig".format(base1) in dockerfile
        assert "COPY {} ./.secret_file".format(base2) in dockerfile

    def test_create_dockerfile_with_copy_files_doesnt_raise_if_file_exists_and_is_same(
        self
    ):
        with tempfile.NamedTemporaryFile() as t1, tempfile.NamedTemporaryFile() as t2:
            docker = DockerEnvironment(
                base_image="python:3.6",
                registry_url="",
                files={t1.name: "/root/dockerconfig", t2.name: "./.secret_file"},
            )

            base1, base2 = os.path.basename(t1.name), os.path.basename(t2.name)

            with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
                shutil.copy(t1.name, os.path.join(tmp, base1))
                docker.create_dockerfile(Flow(name="test"), directory=tmp)

    def test_create_dockerfile_with_copy_files_raises_if_file_exists_and_different(
        self
    ):
        with tempfile.NamedTemporaryFile() as t1, tempfile.NamedTemporaryFile() as t2:
            docker = DockerEnvironment(
                base_image="python:3.6",
                registry_url="",
                files={t1.name: "/root/dockerconfig", t2.name: "./.secret_file"},
            )

            base1, base2 = os.path.basename(t1.name), os.path.basename(t2.name)

            with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
                new_file = os.path.join(tmp, base1)
                shutil.copy(t1.name, new_file)
                with open(new_file, "w+") as f:
                    f.write("a few lines\n")
                with pytest.raises(ValueError) as exc:
                    docker.create_dockerfile(Flow(name="test"), directory=tmp)

        assert "already exists" in str(exc.value)

    def test_init_with_copy_files_raises_informative_error_if_not_absolute(self):
        with pytest.raises(ValueError) as exc:
            docker = DockerEnvironment(
                base_image="python:3.6",
                registry_url="",
                files={
                    ".secret_file": "./.secret_file",
                    "~/.prefect": ".prefect",
                    "/def/abs": "/def/abs",
                },
            )

        file_list = [".secret_file, ~/.prefect", "~/.prefect, .secret_file"]
        assert any(
            [
                "{} are not absolute file paths".format(fs) in str(exc.value)
                for fs in file_list
            ]
        )
