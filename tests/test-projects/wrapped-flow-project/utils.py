from prefect import flow


def pipeline_flow(name=None):
    def setup(__fn):
        return flow(
            __fn,
            name=name,
        )

    return setup
