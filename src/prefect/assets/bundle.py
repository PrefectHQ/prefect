import base64
import zlib
from typing import Any

import orjson

from prefect.assets.core import Asset

BUNDLE_FORMAT_VERSION = "v1"
MAX_ASSETS_PER_BUNDLE = 10_000


def encode_assets(assets: set[Asset]) -> dict[str, Any]:
    """
    Encode assets into a versioned bundle dictionary.
    """
    asset_dicts = [asset.model_dump(exclude_unset=True) for asset in assets][
        :MAX_ASSETS_PER_BUNDLE
    ]

    encoded_data = base64.b64encode(zlib.compress(orjson.dumps(asset_dicts))).decode()

    return {"format": BUNDLE_FORMAT_VERSION, "data": encoded_data}


def decode_assets(bundle: dict[str, Any]) -> set[Asset]:
    """
    Decode a versioned bundle dictionary back into a set of assets.
    """
    if not bundle:
        return set()

    try:
        format_version = bundle.get("format")

        if format_version == "v1":
            encoded_data = bundle.get("data", "")
            if not encoded_data:
                return set()

            asset_dicts = orjson.loads(
                zlib.decompress(base64.b64decode(encoded_data.encode()))
            )
            return {Asset(**asset_dict) for asset_dict in asset_dicts}

        else:
            return set()

    except Exception:
        return set()
