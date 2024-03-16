"""
DEPRECATION WARNING:
This module is deprecated as of March 2024 and will not be available after September 2024.
 """
from prefect.deprecated.packaging.docker import DockerPackager
from prefect.deprecated.packaging.file import FilePackager
from prefect.deprecated.packaging.orion import OrionPackager

# isort: split

# Register any packaging serializers
import prefect.deprecated.packaging.serializers
