import subprocess


# Checks to make sure that collections are loaded prior to attempting to start a worker
def main():
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
