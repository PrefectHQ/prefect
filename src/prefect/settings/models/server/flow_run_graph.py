from pydantic import AliasChoices, AliasPath, Field

from prefect.settings.base import PrefectBaseSettings, _build_settings_config


class ServerFlowRunGraphSettings(PrefectBaseSettings):
    """
    Settings for controlling behavior of the flow run graph
    """

    model_config = _build_settings_config(("server", "flow_run_graph"))

    max_nodes: int = Field(
        default=10000,
        description="The maximum size of a flow run graph on the v2 API",
        validation_alias=AliasChoices(
            AliasPath("max_nodes"),
            "prefect_server_flow_run_graph_max_nodes",
            "prefect_api_max_flow_run_graph_nodes",
        ),
    )

    max_artifacts: int = Field(
        default=10000,
        description="The maximum number of artifacts to show on a flow run graph on the v2 API",
        validation_alias=AliasChoices(
            AliasPath("max_artifacts"),
            "prefect_server_flow_run_graph_max_artifacts",
            "prefect_api_max_flow_run_graph_artifacts",
        ),
    )
