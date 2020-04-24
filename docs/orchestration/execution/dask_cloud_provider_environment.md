# Dask Cloud Provider Environment <Badge text="Cloud"/>

[[toc]]


## Overview

The Dask Cloud Provider Environment runs each Flow on a dynamically created Dask cluster. It uses 
the  [Dask Cloud Provider](https://cloudprovider.dask.org/) project to create a Dask scheduler and
workers using cloud provider services, e.g. AWS Fargate. This Environment aims to provide a very 
easy way to achieve high scalability without the steeper learning curve of Kubernetes.

*IMPORTANT* As of April 19, 2020 the Dask Cloud Provider project contains some
security limitations that make it inappropriate for use with sensitive data.
Until those security items are addressed, this environment should only be used
for prototyping and testing.

## Process

#### Initialization

The `DaskCloudProviderEnvironment` serves largely to pass kwargs through to the specific class
from the Dask Cloud Provider project that you're using. It's a good idea to test Dask Cloud
Provider directly and confirm that it's working correctly before using `DaskCloudProviderEnvironment`.

TODO: Additional details and example usage.
