from typing import Any, Dict

from pydantic import Secret


class SecretDict(Secret[Dict[str, Any]]):
    def __str__(self) -> str:
        return str(self.display_value()) if self.get_secret_value() else ""

    def __repr__(self) -> str:
        return f"SecretDict({self})"

    def display_value(self) -> Dict:
        return {key: "**********" for key in self.get_secret_value().keys()}

    def _display(self) -> dict:
        return self.display_value()
