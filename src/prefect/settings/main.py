from pydantic import model_validator
from pydantic_settings import SettingsConfigDict
from typing_extensions import Self

from .fields import BasePrefectSettings


class PrefectSettings(BasePrefectSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    def to_environment_variables(self, exclude_unset: bool = False) -> dict[str, str]:
        return self.model_dump(
            exclude_none=True, exclude_unset=exclude_unset, mode="json"
        )

    def hash_key(self, exclude_unset: bool = False) -> str:
        return str(
            hash(self.model_dump_json(exclude_unset=exclude_unset, exclude_none=True))
        )

    @model_validator(mode="after")
    def max_log_size_smaller_than_batch_size(self: "Self") -> "Self":
        """
        Validator for settings asserting the batch size and match log size are compatible
        """
        if (
            self.PREFECT_LOGGING_TO_API_BATCH_SIZE
            < self.PREFECT_LOGGING_TO_API_MAX_LOG_SIZE
        ):
            raise ValueError(
                "`PREFECT_LOGGING_TO_API_MAX_LOG_SIZE` cannot be larger than `PREFECT_LOGGING_TO_API_BATCH_SIZE`"
            )
        return self
