import subprocess
import sys


# Checks to make sure that collections are loaded prior to attempting to start a worker
def main():
    raise NotImplementedError(
        "The prefect-kubernetes package hasn't been updated for prefect>=3.0 yet"
    )

    subprocess.check_call(
        ["python", "-m", "pip", "install", "prefect-kubernetes<3"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    try:
        subprocess.check_output(
            ["prefect", "work-pool", "delete", "test-pool"],
        )
    except subprocess.CalledProcessError:
        pass

    try:
        subprocess.check_output(
            ["prefect", "work-pool", "create", "test-pool", "-t", "nonsense"],
        )
    except subprocess.CalledProcessError as e:
        # Check that the error message contains kubernetes worker type
        for type in ["process", "kubernetes"]:
            assert type in str(
                e.output
            ), f"Worker type {type!r} missing from output {e.output}"

    subprocess.check_call(
        ["prefect", "work-pool", "create", "test-pool", "-t", "kubernetes"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
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
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        ["python", "-m", "pip", "uninstall", "prefect-kubernetes", "-y"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        ["prefect", "work-pool", "delete", "test-pool"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


if __name__ == "__main__":
    main()
