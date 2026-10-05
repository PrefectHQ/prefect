# Image for the flow runs these tests submit: a published Prefect image with the
# flows baked in, so flow-run pods need no git checkout or remote storage.
#
# Deployments record their entrypoint relative to WORKDIR, which is where
# `prefect flow-run execute` starts in the pod.
FROM prefecthq/prefect:3-latest

WORKDIR /opt/prefect/flows
COPY flows.py .
