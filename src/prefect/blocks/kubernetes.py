from typing import Dict

import yaml
from kubernetes.client import ApiClient
from kubernetes.config import (
    ConfigException,
    list_kube_config_contexts,
    new_client_from_config_dict,
)

from prefect.blocks.core import Block, register_block


@register_block
class KubernetesClusterConfig(Block):
    """
    A `Block` class for holding information about kubernetes clusters.
    """

    active_config: Dict = None
    config_file_dict: Dict = None
    context: str = None

    @staticmethod
    def get_config_from_dict(contents: Dict, context: str) -> Dict:
        for cluster_config in contents["clusters"]:
            if cluster_config["name"] == context:
                return cluster_config

        raise KeyError(f"No context found in config file with name: {context!r}")

    def load_config_file(self, config_filepath: str):
        with open(config_filepath, "r") as f:
            self.config_file_dict = yaml.safe_load(f)

    @classmethod
    def from_file(cls, config_filepath: str, context: str):
        """
        Factory method to create instance of this block from ~/.kube/config and a context
        """
        with open(config_filepath, "r") as f:
            contents = yaml.safe_load(f)
            cluster_config = cls.get_config_from_dict(
                contents=contents, context=context
            )
            return cls(
                active_config=cluster_config, config_file_dict=contents, context=context
            )

    def use_current_context(self):
        """
        Set the active_config member variable to the currently active k8s context

        list_kube_config_contexts returns a tuple (all_contexts, current_context)
        """
        current_context = list_kube_config_contexts()[1]

        if self.config_file_dict:
            cluster_config = self.get_config_from_dict(
                contents=self.config_file_dict, context=current_context["name"]
            )
            self.active_config = cluster_config

        else:
            raise Exception(
                "No config file provided, call load_config_file on this object"
            )

    def get_api_client(self, context: str, config_filepath: str = None) -> ApiClient:
        """
        Returns an instance of the kubernetes api client with a specific context
        """
        if not config_filepath:
            self.load_config_file(filepath=config_filepath)

        try:
            return new_client_from_config_dict(
                config_dict=self.config_file_dict, context=context
            )
        except ConfigException:
            raise
