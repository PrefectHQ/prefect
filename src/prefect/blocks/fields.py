from typing import Any, Dict

from pydantic import Secret


class SecretDict(Secret[Dict[str, Any]]):
    def _display(self) -> str:
        return (
            str({key: "**********" for key in self.get_secret_value().keys()})
            if self.get_secret_value()
            else ""
        )
