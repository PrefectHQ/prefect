from prefect.deployments import Deployment

# Strings are not valid flow sources
Deployment(name="test", flow="hello!")
