"""
Core set of steps for specifying a Prefect project build step.
"""
import os
import sys
from pathlib import Path

import pendulum

from prefect.docker import build_image, docker_client, get_prefect_image_name
from prefect.utilities.slugify import slugify


def build_docker_image(
    image_name: str,
    dockerfile: str = None,
    auto_build: bool = False,
    tag: str = None,
    push: bool = True,
) -> dict:
    if auto_build:
        lines = []
        base_image = get_prefect_image_name(prefect_version="2.8.5")
        lines.append(f"FROM {base_image}")

        dir_name = os.path.basename(os.getcwd())
        lines.append(f"COPY . /opt/prefect/{dir_name}/")
        lines.append(f"WORKDIR /opt/prefect/{dir_name}/")

        if Path("requirements.txt").exists():
            lines.append("RUN pip install -r requirements.txt")

        dockerfile = Path(".") / "Dockerfile"
        if dockerfile.exists():
            raise ValueError("Dockerfile already exists.")

        with dockerfile.open("w") as f:
            f.writelines(line + "\n" for line in lines)

    try:
        image_id = build_image(
            context=Path("."),
            dockerfile=str(dockerfile),
            pull=True,
            stream_progress_to=sys.stdout,
        )
    finally:
        if auto_build:
            os.unlink(dockerfile)

    if not tag:
        tag = slugify(pendulum.now("utc").isoformat())

    with docker_client() as client:
        image: Image = client.images.get(image_id)
        image.tag(image_name, tag=tag)
    if push:
        events = client.api.push(image_name, tag=tag, stream=True, decode=True)
        try:
            for event in events:
                if "status" in event:
                    sys.stdout.write(event["status"])
                    if "progress" in event:
                        sys.stdout.write(" " + event["progress"])
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                elif "error" in event:
                    raise OSError(event["error"])
        finally:
            client.api.remove_image(f"{image_name}:{tag}", noprune=True)

    return dict(image_name=f"{image_name}:{tag}")
