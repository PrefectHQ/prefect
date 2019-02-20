# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import base64
from typing import List

import cloudpickle
from cryptography.fernet import Fernet

import prefect
from prefect.environments import Environment


class LocalEnvironment(Environment):
    """
    LocalEnvironment is an encrypted and serializable environment for simply packaging
    up flows so they can be stored and transported.
    """

    def __init__(self, encryption_key: bytes = None, serialized_flow: bytes = None):
        if encryption_key is None:
            encryption_key = Fernet.generate_key()
        else:
            try:
                Fernet(encryption_key)
            except Exception:
                raise ValueError("Invalid encryption key.")

        self.encryption_key = encryption_key
        self.serialized_flow = serialized_flow

    def build(self, flow: "prefect.Flow") -> "LocalEnvironment":
        """
        Build the LocalEnvironment. Returns a LocalEnvironment with a serialized flow attribute.

        Args:
            - flow (Flow): The prefect Flow object to build the environment for

        Returns:
            - LocalEnvironment: a LocalEnvironment with a serialized flow attribute
        """
        return LocalEnvironment(
            encryption_key=self.encryption_key,
            serialized_flow=self.serialize_flow_to_bytes(flow),
        )

    def serialize_flow_to_bytes(self, flow: "prefect.Flow") -> bytes:
        """
        Serializes a Flow to binary.

        Args:
            - flow (Flow): the Flow to serialize

        Returns:
            - bytes: the serialized Flow
        """
        pickled_flow = cloudpickle.dumps(flow)
        encrypted_pickle = Fernet(self.encryption_key).encrypt(pickled_flow)
        encoded_pickle = base64.b64encode(encrypted_pickle)
        return encoded_pickle

    def deserialize_flow_from_bytes(self, serialized_flow: bytes) -> "prefect.Flow":
        """
        Deserializes a Flow to binary.

        Args:
            - flow (Flow): the Flow to serialize

        Returns:
            - bytes: the serialized Flow
        """
        decoded_pickle = base64.b64decode(serialized_flow)
        decrypted_pickle = Fernet(self.encryption_key).decrypt(decoded_pickle)
        flow = cloudpickle.loads(decrypted_pickle)
        return flow

    def run(
        self, start_task_ids: List[str] = None, runner_kwargs: dict = None
    ) -> "prefect.engine.state.State":
        """
        Runs the `Flow` represented by this environment.

        Args:
            - start_task_ids (List[str]): A list of Task ids that will be converted to the
                `start_tasks` argument of the `FlowRunner`
            - runner_kwargs (dict): Any arguments for `FlowRunner.run()`.
        """

        runner_kwargs = runner_kwargs or {}

        if not self.serialized_flow:
            raise ValueError(
                "No serialized flow found! Has this environment been built?"
            )
        flow = self.deserialize_flow_from_bytes(self.serialized_flow)
        if start_task_ids is not None:
            if set(start_task_ids).difference(flow.task_ids):
                raise ValueError("Invalid start_task_ids.")
            runner_kwargs["start_tasks"] = [flow.task_ids[i] for i in start_task_ids]
        runner_cls = prefect.engine.get_default_flow_runner_class()
        runner = runner_cls(flow=flow)
        return runner.run(**runner_kwargs)
