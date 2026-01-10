"""Test code_repository_url with serve() method.

Usage:
    uv run python repros/19834_test_serve.py
"""

from prefect import flow, serve


@flow
def hello_world():
    """A simple hello world flow."""
    print("Hello, World!")
    return 42


if __name__ == "__main__":
    # Create deployment with code_repository_url
    deployment = hello_world.to_deployment(
        name="hello-with-repo",
        tags=["test"],
        description="Test deployment with repository URL",
        code_repository_url="https://github.com/PrefectHQ/prefect",  # ✅ New parameter!
    )

    print(f"Deployment name: {deployment.name}")
    print(f"Repository URL: {deployment.code_repository_url}")

    # Uncomment to actually serve (will run indefinitely)
    # serve(deployment)
