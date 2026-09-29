"""Validate the repository-hosted block and worker logo assets."""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
MAPPING = ROOT / "mapping.json"


def main() -> None:
    mapping: dict[str, str] = json.loads(MAPPING.read_text())
    assert mapping
    for filename in mapping.values():
        path = ROOT / filename
        assert path.is_file(), path
        with Image.open(path) as image:
            width, height = image.size
            assert width == height, path
            assert 45 < width < 1000, path
            image.verify()
    assert len(mapping) == len(set(mapping))
    print(
        f"validated {len(set(mapping.values()))} assets for {len(mapping)} Sanity URLs"
    )


if __name__ == "__main__":
    main()
