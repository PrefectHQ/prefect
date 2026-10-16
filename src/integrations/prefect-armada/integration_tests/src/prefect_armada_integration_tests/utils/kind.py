from __future__ import annotations

import hashlib
import ipaddress
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

IMAGE_DIR = Path(__file__).parent.parent / "image"
IMAGE_NAME = "prefect-armada-integration-tests"


def ensure_kind_cluster(name: str) -> None:
    """Ensure the kind cluster hosting Armada exists.

    Unlike a bare Kubernetes cluster, one running Armada cannot be created here:
    it needs Armada and its dependencies deployed on top of it.
    """
    clusters = subprocess.run(
        ["kind", "get", "clusters"], check=True, capture_output=True, text=True
    ).stdout.split()
    if name not in clusters:
        raise RuntimeError(
            f"No kind cluster named {name!r} found (found: {clusters}). Create one "
            "running Armada, for example with `make kind-all` in the "
            "armada-operator repository, or pass `--kind-cluster-name`."
        )
    console.log(f"Using existing kind cluster: {name}")


def build_and_load_flow_image(cluster_name: str) -> str:
    """Build the image holding the test flows and load it into the cluster's nodes.

    Returns the image reference. The tag is derived from the image's sources, so
    a node never runs a stale copy of the flows under an unchanged reference.
    """
    digest = hashlib.sha256()
    for path in sorted(IMAGE_DIR.iterdir()):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    reference = f"{IMAGE_NAME}:{digest.hexdigest()[:12]}"

    console.log(f"Building image: {reference}")
    subprocess.check_call(["docker", "build", "--tag", reference, str(IMAGE_DIR)])
    console.log(f"Loading image into kind cluster: {cluster_name}")
    subprocess.check_call(
        ["kind", "load", "docker-image", reference, "--name", cluster_name]
    )
    return reference


def get_gateway_address(network: str = "kind") -> str | None:
    """Get the IPv4 gateway of the Docker network kind clusters are attached to.

    Pods reach services listening on the host through this address.
    """
    result = subprocess.run(
        [
            "docker",
            "network",
            "inspect",
            network,
            "--format",
            "{{range .IPAM.Config}}{{.Gateway}} {{end}}",
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    # The network has both IPv6 and IPv4 gateways.
    for gateway in result.stdout.split():
        try:
            if ipaddress.ip_address(gateway).version == 4:
                return gateway
        except ValueError:
            continue
    return None
