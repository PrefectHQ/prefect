from pathlib import Path

from prefect.deployments import Deployment

# Invalid
Deployment(name="foo", flow="hello!")

# Valid
Deployment(name="bar", flow={"path": Path(__file__).parent / "single_flow_in_file.py"})
