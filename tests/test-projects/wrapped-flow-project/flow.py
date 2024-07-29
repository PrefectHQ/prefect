from .utils import pipeline_flow


@pipeline_flow(name="wrapped-flow")
def test_flow():
    return "I'm a pipeline flow!"
