from prefect import Task
from pathlib import Path


class FileBase(Task):
    """ This is just a base class to reduce duplicate code. """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _check_target_path(
        self,
        target_directory: Path,
        create_target_if_not_exists: bool,
    ):
        """This checks if the target path exists. If not, target directory will
        be created if create_target_if_not_exists is set to True
        """
        if not target_directory.is_dir():
            if create_target_if_not_exists:
                self.logger.info(f"Creating target directory: {target_directory}")
                target_directory.mkdir()
            else:
                raise ValueError(f"Target directory ({target_directory}) not found!")
