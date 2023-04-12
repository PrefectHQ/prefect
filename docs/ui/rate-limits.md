---
description: Prefect Cloud API rate limits.
tags:
    - API
    - Prefect Cloud
    - rate limits
---

# Prefect Cloud API Rate Limits

API rate limits restrict the number of requests that a single client can make in a given time period. They ensure Prefect Cloud's stability, so that when you make an API call, you always get a response.

!!! info "Prefect Cloud rate limits are subject to change"
    The following rate limits are in effect currently, but are subject to change. Contact Prefect support at [help@prefect.io](mailto:help@prefect.io) if you have questions about current rate limits.

Prefect Cloud enforces the following rate limits: 

- Flow and task creation rate limits
- Log service rate limits
- Service-wide rate limits (applicable to all requests)

## Flow and task creation rate limits

Prefect Cloud limits creation of flow and task runs to: 

- 400 per minute for personal accounts
- 2,000 per minute for organization accounts

The Prefect Cloud API will return a `429` response with an appropriate `Retry-After` header if these limits are triggered.

## Log service rate limits

Prefect Cloud limits the number of logs accepted:

- 700 logs per minute for personal accounts
- 10,000 logs per minute for organization accounts

## Service-wide rate limits

Prefect Cloud also enforces service-wide rate limiting for all API routes. This is intended to protect against high request volumes that may degrade service for all users.

Service-wide rate limits include: 

- 5,000 requests per minute per API key 
- 10,000 requests per minute per client IP

The Prefect Cloud API will return a `429` response if these limits are triggered.