from typing import Dict

import yaml

from prefect.blocks.core import Block, register_block


@register_block
class KubernetesCluster(Block):

    config: Dict = None
    config_file: str
    context: str

    def block_initialization(self) -> None:
        self.config = self.config_dict()
        return super().block_initialization()

    def config_dict(self) -> Dict:
        with open(self.config_file, "r") as f:
            config_contents = yaml.safe_load(f)
            return config_contents
