from pathlib import Path

from prefect import Deployment

Deployment(flow={"path": Path(__file__).parent / "single_flow_in_file.py"})
