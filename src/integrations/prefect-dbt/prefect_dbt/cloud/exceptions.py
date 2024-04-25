class DbtCloudException(Exception):
    """Base class for dbt Cloud exceptions"""


class DbtCloudGetRunFailed(DbtCloudException):
    """Raised when unable to retrieve dbt Cloud run"""


class DbtCloudListRunArtifactsFailed(DbtCloudException):
    """Raised when unable to list dbt Cloud run artifacts"""


class DbtCloudGetRunArtifactFailed(DbtCloudException):
    """Raised when unable to get a dbt Cloud run artifact"""


class DbtCloudJobRunFailed(DbtCloudException):
    """Raised when a triggered job run fails"""


class DbtCloudJobRunCancelled(DbtCloudException):
    """Raised when a triggered job run is cancelled"""


class DbtCloudJobRunTimedOut(DbtCloudException):
    """
    Raised when a triggered job run does not complete in the configured max
    wait seconds
    """


class DbtCloudJobRunTriggerFailed(DbtCloudException):
    """Raised when a dbt Cloud job trigger fails."""


class DbtCloudGetJobFailed(DbtCloudException):
    """Raised when unable to retrieve dbt Cloud job."""


class DbtCloudJobRunIncomplete(DbtCloudException):
    """Raised when a triggered job run is not complete."""
