from typing import Dict

import yaml
from kubernetes.client import ApiClient
from kubernetes.config import new_client_from_config_dict

from prefect.blocks.core import Block, register_block


@register_block
class KubernetesClusterConfig(Block):
    """
    A `Block` class for holding information about kubernetes clusters.
    """

    config: Dict = None
    context: str = None

    @classmethod
    def from_file(cls, filepath: str, context: str):
        """
        Class method to extract dict representing k8s config from config file.
        """
        with open(filepath, "r") as f:
            contents = yaml.safe_load(f)
            for cluster_config in contents["clusters"]:
                if cluster_config["name"] == context:
                    return cls(config=cluster_config, context=context)

        raise KeyError(f"No context found in config file with name: {context!r}")

    # @classmethod
    # def from_current_context(cls):
    #     pass

    def get_client_from_config_dict(self) -> ApiClient:

        try:
            assert self.config

            return new_client_from_config_dict(
                config_dict=self.config, context=self.context
            )

        except AssertionError:
            raise ("config is not populated")
