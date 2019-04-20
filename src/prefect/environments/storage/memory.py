import filecmp
import json
import logging
import os
import shutil
import tempfile
import textwrap
import uuid
from typing import Iterable, List

import docker

import prefect
from prefect.environments.storage import Storage
from prefect.utilities.exceptions import SerializationError


# lastly, the job yml can be populated by CloudEnvironment so that
# run_flow in the CLI command accepts the name of the correct flow.
# cloud-side, agent then calls environment.execute(storage, flow)


class Memory(Storage):
    def get_runner(flow_location):
        # this doesnt make sense for docker
        # returns something with a .run() method
        # that accepts the standard kwargs!!!!!!!
        pass

    def add_flow(flow):
        pass

    @property
    def name(self):
        # name of env (for Docker, full thing)
        pass

    @property
    def flows(self):
        # a dictionary? a set?
        # a way to check whether a flow is in this storage
        # might be tricky to serialize this
        pass

    @property
    def flow_location(self):
        "not sure if property or 'empty' attribute"
        # optionally set at serialization time for an individual flow
        pass

    def get_flow_location(flow):
        # current envs will retrieve by name but don't have to
        pass

    def build(self) -> "Storage":
        # builds with _all_ flows
        pass
