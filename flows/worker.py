import subprocess


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


if __name__ == "__main__":
    main()
