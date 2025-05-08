import subprocess
import time

from kubernetes import client, config
from kubernetes.client.models.v1_job import V1Job
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
K8S_NAMESPACE = "default"


def init_k8s_client() -> client.CoreV1Api:
    """Initialize the Kubernetes client."""
    config.load_kube_config()
    return client.CoreV1Api()


def ensure_kind_cluster(name: str = "prefect-test") -> None:
    """Ensure a kind cluster is running."""
    try:
        clusters = subprocess.run(
            ["kind", "get", "clusters"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        if name not in clusters:
            console.log(f"Creating Kind cluster: {name}")
            subprocess.check_call(["kind", "create", "cluster", "--name", name])
        else:
            console.log(f"Using existing Kind cluster: {name}")

        # Ensure namespace exists
        v1 = init_k8s_client()
        try:
            v1.read_namespace(K8S_NAMESPACE)
        except client.ApiException:
            v1.create_namespace(client.V1Namespace(metadata={"name": K8S_NAMESPACE}))
            console.log(f"Created namespace: {K8S_NAMESPACE}")

    except subprocess.CalledProcessError:
        subprocess.check_call(["kind", "create", "cluster", "--name", name])
        v1 = init_k8s_client()
        v1.create_namespace(client.V1Namespace(metadata={"name": K8S_NAMESPACE}))


def ensure_evict_plugin() -> None:
    """Ensure kubectl-evict-pod plugin is installed."""
    try:
        subprocess.run(
            ["kubectl", "evict-pod", "--help"],
            check=True,
            capture_output=True,
        )
        console.log("[green]kubectl-evict-pod plugin is installed")
    except subprocess.CalledProcessError:
        console.print(
            Panel(
                "[bold red]kubectl-evict-pod plugin is not installed\n"
                "[white]Install it with: [bold]kubectl krew install evict-pod",
                title="Missing Dependency",
            )
        )
        raise RuntimeError(
            "kubectl-evict-pod plugin is not installed - install it with `kubectl krew install evict-pod`"
        )


def get_job_for_flow_run(flow_run_name: str, timeout: int = 60) -> V1Job:
    """Get the job for a flow run."""
    batch_v1 = client.BatchV1Api()
    start_time = time.time()

    with console.status(f"Looking for job for flow run: {flow_run_name}..."):
        while time.time() - start_time < timeout:
            try:
                jobs = batch_v1.list_namespaced_job(K8S_NAMESPACE)
                for job in jobs.items:
                    if job.metadata.name.startswith(flow_run_name):
                        console.log(f"[green]Found job: {job.metadata.name}")
                        return job
            except client.ApiException as e:
                console.log(f"[yellow]Error checking jobs: {e}")

            time.sleep(2)

    raise TimeoutError(
        f"No job found for flow run {flow_run_name} after {timeout} seconds"
    )


def get_job_name(flow_run_name: str, timeout: int = 60) -> str:
    """Get the full job name for a flow run."""
    job = get_job_for_flow_run(flow_run_name, timeout)
    return job.metadata.name


def wait_for_pod(job_name: str, phase: str = "Running", timeout: int = 60) -> str:
    """Wait for a pod matching the job name to be in a given phase."""
    v1 = init_k8s_client()
    start_time = time.time()

    with console.status(f"Waiting for pod for job: {job_name}..."):
        while time.time() - start_time < timeout:
            try:
                pods = v1.list_namespaced_pod(
                    K8S_NAMESPACE,
                    label_selector=f"job-name={job_name}",
                )

                # Look for running pods, newest first
                sorted_pods = sorted(
                    pods.items,
                    key=lambda x: x.metadata.creation_timestamp,
                    reverse=True,
                )

                for pod in sorted_pods:
                    if pod.status.phase == phase:
                        console.log(f"[green]Found pod: {pod.metadata.name}")
                        return pod.metadata.name

            except client.ApiException as e:
                console.log(f"[yellow]Error checking pods: {e}")

            time.sleep(2)

    raise TimeoutError(
        f"No running pod found for job {job_name} after {timeout} seconds"
    )


def evict_pod(pod_name: str) -> None:
    """Evict a specific pod."""
    v1 = init_k8s_client()

    try:
        # Show initial pod state
        pod = v1.read_namespaced_pod(pod_name, K8S_NAMESPACE)

        pod_summary = {
            "Name": pod.metadata.name,
            "Status": pod.status.phase,
            "Node": pod.spec.node_name,
            "Container Status": "Running"
            if pod.status.container_statuses[0].state.running
            else "Not Running",
            "Image": pod.status.container_statuses[0].image,
            "Created": pod.metadata.creation_timestamp,
        }

        table = Table(title="Pod Details Before Eviction")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        for key, value in pod_summary.items():
            table.add_row(key, str(value))

        console.print(table)

        # simulate a pod eviction
        with console.status(f"Evicting pod {pod_name}..."):
            subprocess.check_call(
                ["kubectl", "evict-pod", pod_name, "-n", K8S_NAMESPACE]
            )
            console.print(f"[bold green]Pod {pod_name} evicted successfully")

    except (client.ApiException, subprocess.CalledProcessError) as e:
        console.print(f"[bold red]Failed to evict pod: {e}")
        raise


def delete_pods() -> None:
    """Delete all pods in the default namespace."""
    v1 = init_k8s_client()
    v1.delete_collection_namespaced_pod(K8S_NAMESPACE)
