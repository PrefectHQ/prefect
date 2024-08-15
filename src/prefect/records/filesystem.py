from pathlib import Path
from typing import Optional

from prefect.records.base import RecordStore, TransactionRecord
from prefect.results import BaseResult
from prefect.settings import PREFECT_HOME
from prefect.transactions import IsolationLevel


class FileSystemRecordStore(RecordStore):
    def __init__(self, records_directory: Optional[Path] = None):
        self.records_directory = records_directory or (PREFECT_HOME.value() / "records")

    def _ensure_records_directory_exists(self):
        self.records_directory.mkdir(parents=True, exist_ok=True)

    def read(self, key: str) -> Optional[TransactionRecord]:
        if not self.exists(key):
            return None
        record_data = self.records_directory.joinpath(key).read_text()
        return TransactionRecord(
            key=key, result=BaseResult.model_validate_json(record_data)
        )

    def write(self, key: str, result: BaseResult, holder: Optional[str] = None) -> None:
        self._ensure_records_directory_exists()
        path = self.records_directory.joinpath(key)
        path.touch(exist_ok=True)
        record_data = result.model_dump_json()
        path.write_text(record_data)

    def exists(self, key: str) -> bool:
        return self.records_directory.joinpath(key).exists()

    def supports_isolation_level(self, isolation_level: IsolationLevel) -> bool:
        return isolation_level in {
            IsolationLevel.READ_COMMITTED,
            IsolationLevel.SERIALIZABLE,
        }
