import bloop

from .utils import pipeline_flow


@pipeline_flow(name="wrapped-flow")
def bloop_flow(bloop: bloop.Bloop = bloop.DEFAULT):
    return "I do a thing with bloop!"
