from typing import Dict

import yaml
from kubernetes.client import ApiClient
from kubernetes.config import list_kube_config_contexts, new_client_from_config_dict

from prefect.blocks.core import Block, register_block


@register_block
class KubernetesClusterConfig(Block):
    """
    A `Block` class for holding information about kubernetes clusters.
    """

    config: Dict = None
    context: str = None

    def get_config_by_context(self, contents: Dict, context: str) -> Dict:
        for cluster_config in contents["clusters"]:
            if cluster_config["name"] == context:
                return cluster_config

        raise KeyError(f"No context found in config file with name: {context!r}")

    @classmethod
    def from_file(cls, filepath: str, context: str):
        """
        Class method to extract dict representing k8s config from config file.
        """
        with open(filepath, "r") as f:
            contents = yaml.safe_load(f)
            cluster_config = cls.get_config_by_context(
                contents=contents, context=context
            )
            return cls(config=cluster_config, context=context)

    @classmethod
    def from_current_context(cls):
        # list_kube_config_contexts returns a tuple (all_context, current)
        current_context = list_kube_config_contexts()[1]

        if cls.config:
            cluster_config = cls.get_config_by_context(
                contents=cls.config, context=current_context
            )
            return cls(config=cluster_config, context=current_context)
        else:
            raise AssertionError

    def get_client_from_config_dict(self) -> ApiClient:

        try:
            assert self.config

            return new_client_from_config_dict(
                config_dict=self.config, context=self.context
            )

        except AssertionError:
            raise ("config is not populated")
