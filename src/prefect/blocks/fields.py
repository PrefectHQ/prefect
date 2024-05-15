from typing import Any, Dict

from pydantic import Secret


class SecretDict(Secret[Dict[str, Any]]):
    def __str__(self) -> str:
        return (
            str({key: "**********" for key in self.get_secret_value().keys()})
            if self.get_secret_value()
            else ""
        )

    def __repr__(self) -> str:
        return f"SecretDict({self})"

    def dict(self) -> Dict:
        return {key: "**********" for key in self.get_secret_value().keys()}
