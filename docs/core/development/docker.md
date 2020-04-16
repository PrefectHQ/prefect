# Docker

Prefect provides Docker images for master builds and versioned releases [here](https://hub.docker.com/r/prefecthq/prefect).

To run the latest Prefect Docker image:

```bash
docker run -it prefecthq/prefect:latest
```

Image tag breakdown:

| Tag              |     Prefect Version      | Python Version |
| ---------------- | :----------------------: | -------------: |
| latest           | most recent PyPi version |            3.7 |
| master           |       master build       |            3.7 |
| latest-python3.8 | most recent PyPi version |            3.8 |
| latest-python3.7 | most recent PyPi version |            3.7 |
| latest-python3.6 | most recent PyPi version |            3.6 |
| X.Y.Z-python3.8  |          X.Y.Z           |            3.8 |
| X.Y.Z-python3.7  |          X.Y.Z           |            3.7 |
| X.Y.Z-python3.6  |          X.Y.Z           |            3.6 |
