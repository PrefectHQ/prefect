import subprocess
import sys
from pathlib import Path

default_target = Path(__file__).parent
targets = []
options = []

for arg in sys.argv[1:] if len(sys.argv) > 1 else []:
    if arg.startswith("-"):
        options.append(arg)
    else:
        if not Path(arg).exists() and (default_target / arg).exists():
            arg = str(default_target / arg)
        targets.append(arg)


process = subprocess.run(
    [
        "pytest",
        "--no-cov",
        # TODO: These should be overridable
        "--benchmark-group-by=func",
        "--benchmark-columns=mean,stddev,min,max,rounds",
        "--benchmark-sort=mean",
        "--benchmark-min-rounds=1",
    ]
    + (targets or [default_target])
    + options,
    stdout=sys.stdout,
    stderr=sys.stderr,
)


sys.exit(process.returncode)
