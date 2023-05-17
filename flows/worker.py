import prefect
import subprocess
from packaging.version import Version


# Checks to make sure that collections are loaded prior to attempting to start a worker
def main():
    # Worker CLI was introduced in 2.8.0
    if Version(prefect.__version__) > Version("2.7"):
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
