from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(
            "Expected one argument: the Prefect engine startup marker path.",
            file=sys.stderr,
        )
        return 2

    Path(args[0]).touch()
    os.execv(sys.executable, [sys.executable, "-m", "prefect.engine"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
