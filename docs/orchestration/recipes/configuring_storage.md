# Configuring Docker Storage

This recipe is for configuring your Flow's [Docker storage object](/api/latest/storage.html#docker) to handle potentially complicated non-Python dependencies. This is useful to understand for Flows which rely on complex environments to run successfully; for example if your Flow uses:
- database drivers
- reliance on C bindings for file-types such as HDF files
- special environment variables
- special configuration files
- subprocess calls to non-Python CLIs
- special proprietary Python scripts or packages

Then you most likely will need to configure the Docker image in which your Flow lives.

[[toc]]

### Building a custom base image

As a motivating example, let's consider the case where we have an ETL Flow that talks to a Microsoft SQL Server Database through [`pyodbc`](https://github.com/mkleehammer/pyodbc).  The first thing you might notice is that this introduces a dependency on a Python package that is not required by Prefect.  To ensure such a requirement is always added into your Flow's Docker image, we can use the `python_dependencies` keyword argument:

```python
from prefect.storage import Docker

# Create our Docker storage object
storage = Docker(registry_url="gcr.io/dev/", python_dependencies=["pyodbc"])
```

If we attempt a dry-run build of this docker image by calling `storage.build()`, we'd probably encounter the following error:
```
  gcc: error trying to exec 'cc1plus': execvp: No such file or directory
  error: command 'gcc' failed with exit status 1
  ----------------------------------------

  Running setup.py clean for pyodbc
  ERROR: Failed building wheel for pyodbc
```

Without going into unnecessary detail, this is because the default base image for Prefect Flows is minimal and doesn't include whatever non-Python bindings the `pyodbc` package requires. To add such dependencies, we will need to configure an appropriate base image to use for our Flow.  For both reference and completeness, the following [Dockerfile](https://docs.docker.com/engine/reference/builder/) will build a base image that allows our Flow to connect to Microsoft SQL Server through `pyodbc`:

```
FROM prefecthq/prefect:latest-python3.7

# install some base utilities
RUN apt update && apt install build-essential -y build-essential unixodbc-dev && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install curl -y

# install mssql-tools
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update && ACCEPT_EULA=Y apt-get install msodbcsql17 -y
RUN ACCEPT_EULA=Y apt-get install mssql-tools -y

# update bash configuration
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc

# update OpenSSL configuration file
RUN sed -i 's/TLSv1\.2/TLSv1.0/g' /etc/ssl/openssl.cnf
RUN sed -i 's/DEFAULT@SECLEVEL=2/DEFAULT@SECLEVEL=1/g' /etc/ssl/openssl.cnf
```

Note that we used `python3.7` above, but you should attempt to match the version of Python you used in building your flow.
::: tip What types of Docker images are allowed as base images?
Note that the _only_ universal requirement for your Flow's Docker images are that the Prefect python package can be installed into them (note that Prefect will attempt to install itself at build time if your base image doesn't already have it installed).
:::

::: warning Prefect defaults
Prefect attempts to infer sensible defaults for as much as it can, including the version of Python you are using and the version of Prefect.  Additionally, Prefect attempts to run various "healthchecks" which ensure your Flow's Docker image is compatible with your Flow code.  However, there is only so much Prefect can infer - if your Flow requires complicated dependencies you may need to experiment with various Docker images.
:::

For completeness sake, we would perform the following steps to register this Flow using a configured Docker storage object:
- save the above Dockerfile script into a file called `Dockerfile`
- run a command like `docker build . -t myregistryurl/imagename:imagetag`
- provide `myregistryurl/imagename:imagetag` as the `base_image` to `Docker` storage above

Note that you don't necessarily need to push your custom base image to a registry; as long as it resides on the machine that you register from, your Docker daemon will be able to use it as your Flow's base image.

### Providing the Dockerfile <Badge text="0.7.2+"/>

The `base_image` pattern above is maximally useful when you register multiple Flows that share a common set of dependencies.  However, as of Prefect 0.7.2 you don't have to build an intermediate image to configure your Flow's storage!  Using the above example, we can avoid the intermediate step by storing the `Dockerfile` and pointing to its location using the `dockerfile` keyword argument:
```python
from prefect.storage import Docker

# Create our Docker storage object
storage = Docker(registry_url="gcr.io/dev/",
                 python_dependencies=["pyodbc"],
                 dockerfile="/path/to/Dockerfile")
```

### Including other Python scripts

Another common situation is when your Flow imports objects or functions from other Python files that are not included in a publicly available Python package.  Unsurprisingly, your Flow will need to be able to make the same imports within your Docker image.  In order to accomodate this, you generally have two options:

1. Package your scripts up into a true [Python package](https://realpython.com/python-modules-packages/).  You will most likely need to use the `COPY` instruction to put your package into the image, and then the `RUN` instruction to install it.  This pattern will generally require using an intermediate base image so that you have full control over your [docker build context](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/).
2. Use the `files` keyword argument to Prefect's Docker storage object to copy individual files into your image, and then add these files to your image's `PYTHONPATH` environment variable (either through the `env_vars` keyword argument or by building a base image and using the `ENV` docker instruction).  This ensures these scripts can be imported from regardless of the present working directory of your Flow.
