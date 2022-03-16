---
description: Tips for troubleshooting common development mistakes and error situations.
tags:
    - contributing
    - development
    - troubleshooting
    - errors
---

# Troubleshooting

This section provides tips for troubleshooting and resolving common development mistakes and error situations.

## API tests return an unexpected 307 Redirected

**Summary:** Requests require a trailing `/` in the request URL.

If you write a test that does not include a trailing `/` in the request URL:

```python
async def test_example(client):
    response = await client.post("/my_route")
    assert response.status_code == 201
```

You'll see a failure like:

```
E       assert 307 == 201
E        +  where 307 = <Response [307 Temporary Redirect]>.status_code
```

To resolve this, include the trailing `/`:

```python
async def test_example(client):
    response = await client.post("/my_route/")
    assert response.status_code == 201
```

**Reference:** "HTTPX disabled redirect following by default" in [`0.22.0`](https://github.com/encode/httpx/blob/master/CHANGELOG.md#0200-13th-october-2021).