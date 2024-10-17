import subprocess
import sys


def sigterm_serve_and_check_output():
    # Start the script as a subprocess
    process = subprocess.Popen(
        [sys.executable, "flows/serve_a_flow.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    expected_outputs = [
        "All deployments have been paused!",
        "Received KeyboardInterrupt, shutting down...",
        "Successfully completed and audited",
    ]
    found_outputs = [False] * len(expected_outputs)

    full_output = []
    assert process.stdout is not None, "No stdout found"
    for line in process.stdout:
        print(line, end="")  # Print each line as it comes
        full_output.append(line)
        for i, expected in enumerate(expected_outputs):
            if expected in line:
                found_outputs[i] = True

    process.wait()

    for expected, found in zip(expected_outputs, found_outputs):
        assert found, f"Expected '{expected}' not found in output"

    print("Integration test passed successfully!")


if __name__ == "__main__":
    sigterm_serve_and_check_output()
