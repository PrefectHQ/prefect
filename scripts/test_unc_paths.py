import os
import sys
from pathlib import Path

from prefect import flow
from prefect.flows import Flow


def setup_unc_share(base_path: Path) -> Path:
    """
    Creates a test UNC path and returns it.
    Requires admin privileges on Windows.
    """
    if os.name != "nt":
        print("This script only works on Windows")
        sys.exit(1)

    # Create a test directory structure in the share
    unc_path = Path(r"\\localhost\PrefectTest")

    # Create a src directory in the share for our test flow
    src_dir = unc_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    return unc_path


def create_test_flow_file(path: Path):
    """Create a test flow file in the given path"""
    flow_code = """
from prefect import flow

@flow
def remote_test_flow(name: str = "remote"):
    print(f"Hello from {name} in remote flow!")
    return "Remote Success!"
"""
    # Create the flow file in src/app.py
    flow_file = path / "src" / "app.py"
    flow_file.write_text(flow_code)
    return flow_file


if __name__ == "__main__":
    try:
        # Setup UNC share
        unc_path = setup_unc_share(Path.cwd())
        print(f"Created UNC path structure at: {unc_path}")

        # Create a test flow file in the share
        flow_file = create_test_flow_file(unc_path)
        print(f"Created test flow file at: {flow_file}")

        # Try to load and run flow from UNC path
        print("Attempting to load flow from UNC path...")
        remote_flow = flow.from_source(
            source=unc_path, entrypoint="src/app.py:remote_test_flow"
        )

        print("Testing if flow was loaded correctly...")
        assert isinstance(remote_flow, Flow), "Flow was not loaded correctly"
        print("Flow loaded successfully!")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        raise
