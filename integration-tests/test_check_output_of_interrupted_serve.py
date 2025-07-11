import sys
from io import StringIO
from pathlib import Path

from prefect.utilities.processutils import run_process


async def test_check_output_of_interrupted_serve():
    python_executable = sys.executable

    stderr_buffer = StringIO()

    command = [
        python_executable,
        str(Path(__file__).parent.resolve() / "serve_a_flow.py"),
    ]

    print(f"Running command: {command}")

    await run_process(command, stream_output=(None, stderr_buffer))

    # Get the captured output as strings
    stderr_output = stderr_buffer.getvalue()

    # Define the expected messages
    expected_messages = [
        "prefect.runner - Pausing all deployments...",
        "prefect.flows - Received KeyboardInterrupt, shutting down...",
    ]

    unexpected_messages = [
        "raise KeyboardInterrupt()",
    ]

    # Check if each expected message is in the corresponding line
    for expected in expected_messages:
        assert expected in stderr_output, (
            f"Expected '{expected}' not found in '{stderr_output}'"
        )

    for unexpected in unexpected_messages:
        assert unexpected not in stderr_output, (
            f"Unexpected '{unexpected}' found in '{stderr_output}'"
        )

    print("All expected log messages were found")
