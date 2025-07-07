
FROM prefecthq/prefect:3-latest
COPY flows/docker_deploy.py /opt/prefect/flows/docker_deploy.py
