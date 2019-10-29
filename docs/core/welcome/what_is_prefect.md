---
sidebarDepth: 0
---

# What is Prefect?

Running code is easy.

Running workflows is hard.

That's why we built [**Prefect Core**](https://github.com/prefecthq/prefect), an open-source automation and scheduling engine.

Prefect is a framework for taking any code and transforming it into a robust, distributed workflow. It includes the tools to design, build, test, and run powerful data applications. As an engine and an API, it codifies the best practices of data engineering.

Along with [**Prefect Cloud**](https://www.prefect.io/cloud-access), the Prefect platform represents a full negative engineering solution for data scientists and engineers.

## Positive and negative engineering

As data scientists and engineers, we distinguish between [**positive** and **negative** engineering](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d).

**Positive engineering** refers to all the code we _want_ to write: the analysis, the model, the ETL, the transformation, the orchestration, the request, etc. Broadly, these are _things we need to do to achieve an objective_.

**Negative engineering** is all the code we write to make sure the positive code runs: the scheduling, the parameterization, the execution, the logging, the error trapping, the alerts, the retries, the lineage, the infrastructure, the data serialization, and the API. These are _things we need to make sure our code runs and defend against unexpected failures_.

Prefect is a framework for negative engineering. It takes any code and transforms it into a robust workflow.

As a negative engineering framework, Prefect is agnostic to positive engineering use cases. It plays nicely with any third-party code or external systems. Here are a few ways in which Prefect has been deployed:

- turning on a coffee machine every morning
- parsing terabytes of satellite imagery
- ETL from databases to data warehouses
- allowing QA checks during data loads
- powering a Slackbot
- deploying parameterized machine learning models
- microbatch processing of Kafka streams
- running backtests of quantitative investment systems
- orchestrating Spark jobs
- performing database backups
- running maintenance on Prefect Cloud
- sending new-user confirmation emails
- retraining machine learning models

What will you build?
