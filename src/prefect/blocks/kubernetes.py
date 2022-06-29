from pathlib import Path
from typing import Dict

import yaml
from kubernetes.client import ApiClient
from kubernetes.config.kube_config import (
    ConfigException,
    list_kube_config_contexts,
    load_kube_config_from_dict,
    new_client_from_config_dict,
)

from prefect.blocks.core import Block, register_block

KUBE_CONFIG_DEFAULT_LOCATION = f"{Path.home()}/.kube/config"


@register_block
class KubernetesClusterConfig(Block):
    """
    A `Block` class for holding information about kubernetes clusters.
    """

    config: Dict
    context: str = None

    @staticmethod
    def get_config_from_dict(contents: Dict, context: str) -> Dict:
        for cluster_config in contents["clusters"]:
            if cluster_config["name"] == context:
                return cluster_config

        raise KeyError(f"No context found in config file with name: {context!r}")

    @classmethod
    def from_file(cls, path: str, context: str = None):
        """
        Factory method to create instance of this block from a ~/.kube/config and a context

        list_kube_config_contexts returns a tuple (all_contexts, current_context)

        """

        if not context:
            context = list_kube_config_contexts()[1]

        with open(path, "r") as f:
            contents = yaml.safe_load(f)
            cluster_config = cls.get_config_from_dict(
                contents=contents, context=context["name"]
            )

        return cls(config=cluster_config, context=context["name"])

    @classmethod
    def from_environment(cls):
        """
        Factory method to produce an instance of this class using the default kube config location
        """

        return cls.from_file(path=KUBE_CONFIG_DEFAULT_LOCATION)

    def get_api_client(self) -> ApiClient:
        """
        Returns an instance of the kubernetes api client with a specific context
        """
        try:
            return new_client_from_config_dict(
                config_dict=self.config, context=self.context
            )
        except ConfigException:
            raise

    def activate(self) -> None:
        """
        Convenience method for activating the
        """

        load_kube_config_from_dict(
            config_dict=self.config,
            context=self.context,
        )
