# `prefect-aws`

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-aws/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-aws?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-aws/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-aws?color=26272B&labelColor=090422" /></a>
</p>

## Welcome

`prefect-aws` makes it easy to leverage the capabilities of AWS in your flows, featuring support for ECS, S3, Secrets Manager, and Batch.

### Installation

To start using `prefect-aws`:

```bash
pip install prefect-aws
```

### Docker Images

Pre-built Docker images with `prefect-aws` are available for simplified deployment:

```bash
docker pull prefecthq/prefect-aws:latest
```

#### Available Tags

Images are tagged with clear version information:
- `prefecthq/prefect-aws:latest` - Latest stable release (Python 3.12)
- `prefecthq/prefect-aws:latest-python3.11` - Latest stable with Python 3.11
- `prefecthq/prefect-aws:0.5.9-python3.12` - Specific prefect-aws version with Python 3.12
- `prefecthq/prefect-aws:0.5.9-python3.12-prefect3.4.9` - Full version specification

#### Usage Examples

**Running an ECS worker:**
```bash
docker run -d \
  --name prefect-ecs-worker \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/your-account/workspaces/your-workspace \
  -e PREFECT_API_KEY=your-api-key \
  prefecthq/prefect-aws:latest \
  prefect worker start --pool ecs-pool
```

**Local development:**
```bash
docker run -it --rm \
  -v $(pwd):/opt/prefect \
  prefecthq/prefect-aws:latest \
  python your_flow.py
```
