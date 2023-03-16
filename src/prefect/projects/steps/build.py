"""
Core set of steps for specifying a Prefect project build step.
"""
import sys
from pathlib import Path

import pendulum

from prefect.docker import build_image, docker_client
from prefect.utilities.slugify import slugify


def build_docker_image(
    image_name: str, dockerfile: str = None, tag: str = None, push: bool = True
) -> dict:
    image_id = build_image(
        context=Path("."),
        dockerfile=dockerfile,
        pull=True,
        stream_progress_to=sys.stdout,
    )

    if not tag:
        tag = slugify(pendulum.now("utc").isoformat())

    if push:
        with docker_client() as client:
            image: Image = client.images.get(image_id)
            image.tag(image_name, tag=tag)
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
