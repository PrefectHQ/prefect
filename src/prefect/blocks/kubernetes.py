from pathlib import Path
from typing import Dict

import yaml
from kubernetes.client import ApiClient
from kubernetes.config.kube_config import (
    KUBE_CONFIG_DEFAULT_LOCATION,
    list_kube_config_contexts,
    load_kube_config_from_dict,
    new_client_from_config_dict,
)
from pydantic import validate_arguments

from prefect.blocks.core import Block, register_block


@register_block
class KubernetesClusterConfig(Block):
    """
    A `Block` class for holding information about kubernetes clusters.
    """

    config: Dict
    context: str = None

    @classmethod
    @validate_arguments
    def from_file(cls, path: Path, context: str = None):
        """
        Factory method to create instance of this block from a ~/.kube/config and a context

        list_kube_config_contexts returns a tuple (all_contexts, current_context)

        """
        existing_contexts, current_context = list_kube_config_contexts(
            config_file=str(path)
        )

        if context:
            if context not in [i["name"] for i in existing_contexts]:
                raise ValueError(f"No such context in {path}: {context}")
        else:
            context = current_context["name"]

        config_file_contents = path.read_text()
        config_dict = yaml.safe_load(config_file_contents)

        return cls(config=config_dict, context=context)

    @classmethod
    def from_default_kube_config(cls):
        """
        Factory method to produce an instance of this class using the default kube config location
        """

        return cls.from_file(path=KUBE_CONFIG_DEFAULT_LOCATION)

    def get_api_client(self) -> ApiClient:
        """
        Returns an instance of the kubernetes api client with a specific context
        """
        return new_client_from_config_dict(
            config_dict=self.config, context=self.context
        )

    def activate(self) -> None:
        """
        Convenience method for activating the k8s config stored in an instance of this block
        """
        load_kube_config_from_dict(
            config_dict=self.config,
            context=self.context,
        )
