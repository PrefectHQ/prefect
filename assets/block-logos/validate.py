"""Validate the repository-hosted block and worker logo assets."""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
MAPPING = ROOT / "mapping.json"


def reject_duplicate_keys(pairs: list[tuple[str, str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for key, value in pairs:
        assert key not in mapping, key
        mapping[key] = value
    return mapping


def main() -> None:
    mapping: dict[str, str] = json.loads(
        MAPPING.read_text(), object_pairs_hook=reject_duplicate_keys
    )
    assert mapping
    for filename in mapping.values():
        path = ROOT / filename
        assert path.is_file(), path
        with Image.open(path) as image:
            width, height = image.size
            assert (width, height) == (256, 256), path
            assert image.format == "PNG", path
            assert image.mode == "RGBA", path
            image.verify()
    assert len(mapping) == len(set(mapping))
    print(
        f"validated {len(set(mapping.values()))} assets for {len(mapping)} Sanity URLs"
    )


if __name__ == "__main__":
    main()
