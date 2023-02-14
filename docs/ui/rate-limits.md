---
description: Prefect Cloud API rate limits.
tags:
    - API
    - Prefect Cloud
    - rate limits
---

# Prefect Cloud API Rate Limits

An API rate limit is a way for Prefect to ensure the stability of the Prefect Cloud platform. API rate limits enable us to control the number of requests any given app can make on the platform. It ensures that, when you make an API call, you get a response.

!!! info "Prefect Cloud rate limits are subject to change"
    The following rate limits are in effect currently, but are subject to change. Contact Prefect support at [help@prefect.io](mailto:help@prefect.io) if you have questions about current rate limits.

Prefect Cloud enforces the following rate limits: 

- Flow and task creation rate limits
- Log service rate limits
- Service-wide rate limits (applies to all requests)

## Flow and task creation rate limits

We limit creation of flow and task runs to: 

- 2,000 per minute per account

The Prefect Cloud API will return a `429` response with an appropriate `Retry-After` header if these limits are triggered.

## Log service rate limits

The `logs` service enforces limits on the number of logs sent. 

- 700 logs per minute for personal accounts
- 10,000 logs per minute for organization accounts

## Service-wide rate limits

Prefect also enforces service-wide rate limiting for all Prefect Cloud API routes. This is intended to protect against high request volumes that may degrade service for all users. Service-wide rate limits apply to all routes.

Service-wide rate limits include: 

- 5,000 requests per minute per API key 
- 10,000 requests per minute per client IP

The Prefect Cloud API will return a `429` response if these limits are triggered.