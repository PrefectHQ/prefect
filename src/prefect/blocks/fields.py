from typing import Any, Dict

from pydantic import Secret


class SecretDict(Secret[Dict[str, Any]]):
    pass
