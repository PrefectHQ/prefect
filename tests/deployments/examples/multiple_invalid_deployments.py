from prefect.deployments import Deployment

Deployment(name="foo", flow="hello!")
Deployment(name="bar", flow="goodbye!")
