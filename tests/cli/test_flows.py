import subprocess
import tempfile
import pytest
import json
import prefect
from cryptography.fernet import Fernet


class SuccessTask(prefect.Task):
    def run(self):
        return 1


class PlusOneTask(prefect.Task):
    def run(self, x):
        return x + 1


class AddTask(prefect.Task):
    def run(self, x, y):
        return x + y


@pytest.fixture(autouse=True)
def clear_registry():
    yield
    prefect.build.registry.REGISTRY.clear()


def run_with_startup_registry(cli_command):
    """
    Runs a cli_command in a subprocess with environment variables set that let the
    subprocess' Prefect instance load the current registry object.
    """
    encryption_key = Fernet.generate_key().decode()
    with tempfile.NamedTemporaryFile() as tmp:
        with open(tmp.name, "wb") as f:
            f.write(
                prefect.build.registry.serialize_registry(encryption_key=encryption_key)
            )

        env = [
            'PREFECT__REGISTRY__LOAD_ON_STARTUP="{}"'.format(tmp.name),
            'PREFECT__REGISTRY__ENCRYPTION_KEY="{}"'.format(encryption_key),
        ]

        return subprocess.check_output(" ".join(env + [cli_command]), shell=True)


def run_with_registry_option(cli_command):
    """
    Runs a cli_command in a subprocess with command line flags for the registry
    """
    encryption_key = Fernet.generate_key().decode()
    with tempfile.NamedTemporaryFile() as tmp:
        with open(tmp.name, "wb") as f:
            f.write(
                prefect.build.registry.serialize_registry(encryption_key=encryption_key)
            )
        options = "--registry-path={} --registry-encryption-key={}".format(
            tmp.name, encryption_key
        )

        if cli_command.lower().startswith("prefect "):
            cmd = "prefect " + options + " " + cli_command.split("prefect ", 1)[1]

        return subprocess.check_output(cmd, shell=True)


def test_flows_keys_empty_registry():
    output = json.loads(
        subprocess.check_output("prefect flows keys", shell=True).decode()
    )
    assert output == []


@pytest.mark.parametrize(
    "subprocess_fn", [run_with_registry_option, run_with_startup_registry]
)
def test_flows_keys(subprocess_fn):
    f1 = prefect.Flow(register=True)
    f2 = prefect.Flow(name="hi", version="1", register=True)
    f3 = prefect.Flow(name="hi", version="2", register=True)

    output = json.loads(subprocess_fn("prefect flows keys").decode())
    keys = ["project", "name", "version"]
    assert output == [dict(zip(keys, f.key())) for f in [f1, f2, f3]]

@pytest.mark.parametrize(
    "subprocess_fn", [run_with_registry_option, run_with_startup_registry]
)

def test_flows_runs(subprocess_fn):
    """
    Tests that the CLI runs a flow by creating a flow that writes to a known file and testing that the file is written.
    """

    @prefect.task
    def write_to_file(path):
        with open(path, "w") as f:
            f.write("1")

    with tempfile.NamedTemporaryFile() as tmp:
        with prefect.Flow(register=True) as f:
            write_to_file(tmp.name)

        subprocess_fn("prefect flows run Flows Flow 1")

        with open(tmp.name, "r") as f:
            assert f.read() == "1"
