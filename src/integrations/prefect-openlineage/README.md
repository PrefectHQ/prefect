# prefect-openlineage

<p align="center">
    <!--- Insert a cover image here -->
    <!--- <br> -->
    <a href="https://pypi.python.org/pypi/prefect-openlineage/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-openlineage?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-openlineage/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-openlineage?color=26272B&labelColor=090422" /></a>
</p>

## Basic Configuration

At a minimum, the integration requires the user to define a transport and Prefect API URL, both of which can be supplied using environment variables.

For example:

```sh
export OPENLINEAGE__TRANSPORT__TYPE='http' &&
export OPENLINEAGE__TRANSPORT__URL='http://lineageconsumer.com:5000' &&
export OPENLINEAGE__TRANSPORT__ENDPOINT='/api/v1/lineage' &&
export PREFECT_API_URL='http://prefectserver.com:4200/api'
```

For more details about OpenLineage transport options and how to configure them, consult the [OpenLineage Python Client Documentation](https://openlineage.io/docs/client/python/).

Specifying a namespace for jobs is strongly recommended:

```sh
export OPENLINEAGE_NAMESPACE='prefect_test'
```

See the docs at [https://docs.prefect.io/integrations/prefect-openlineage](https://docs.prefect.io/integrations/prefect-openlineage) for more information.
