import os
import prefect
import subprocess
from packaging.version import Version


# Checks to make sure that collections are loaded prior to attempting to start a worker
def main():
    TEST_SERVER_VERSION = os.environ.get("TEST_SERVER_VERSION")
    # Work pool became GA in 2.8.0
    if Version(prefect.__version__) >= Version("2.8") and Version(
        TEST_SERVER_VERSION
    ) >= Version("2.8"):
        subprocess.check_call(["python", "-m", "pip", "install", "prefect-kubernetes"])
        subprocess.check_call(
            [
                "prefect",
                "worker",
                "start",
                "-p",
                "test-pool",
                "-t",
                "kubernetes",
                "--run-once",
            ]
        )
        subprocess.check_call(
            ["python", "-m", "pip", "uninstall", "prefect-kubernetes", "-y"]
        )


if __name__ == "__main__":
    main()
