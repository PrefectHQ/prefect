# Eagerly import the legacy submodules so that
# `prefect_aws.experimental.bundles.upload` and `.execute` are bound as
# package attributes during import — preserving the legacy
# submodule-attribute access pattern. The submodules themselves emit
# deprecation warnings on import.
from . import execute, upload  # noqa: F401
