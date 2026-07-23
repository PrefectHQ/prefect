from __future__ import annotations

import sys
from pathlib import Path

# Ensure the package source directory is on sys.path during test collection.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
