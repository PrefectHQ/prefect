---
description: Tips for troubleshooting common development mistakes and error situations.
tags:
    - contributing
    - development
    - troubleshooting
    - errors
---

# Troubleshooting

This section provides tips for troubleshooting and resolving common development mistakes
and error situations.

## API tests return an unexpected 307 Redirected

**Summary:** Requests require a trailing `/` in the request URL.

If you write a test that does not include a trailing `/` when making a request to a specific endpoint:

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

Note: requests to nested URLs may exhibit the *opposite* behavior and require no trailing slash:
```python
async def test_nested_example(client):
    response = await client.post("/my_route/filter/")
    assert response.status_code == 307

    response = await client.post("/my_route/filter")
    assert response.status_code == 200
```

**Reference:** "HTTPX disabled redirect following by default" in [`0.22.0`](https://github.com/encode/httpx/blob/master/CHANGELOG.md#0200-13th-october-2021).


## `pytest.PytestUnraisableExceptionWarning` or `ResourceWarning`

As you're working with one of the `FlowRunner` implementations, you may get a surprising
error like:

```
E               pytest.PytestUnraisableExceptionWarning: Exception ignored in: <ssl.SSLSocket fd=-1, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0>
E
E               Traceback (most recent call last):
E                 File ".../pytest_asyncio/plugin.py", line 306, in setup
E                   res = await func(**_add_kwargs(func, kwargs, event_loop, request))
E               ResourceWarning: unclosed <ssl.SSLSocket fd=10, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('127.0.0.1', 60605), raddr=('127.0.0.1', 6443)>

.../_pytest/unraisableexception.py:78: PytestUnraisableExceptionWarning
```

This is saying that your test suite (or the `prefect` library code) opened a
connection to something (like a Docker daemon or a Kubernetes cluster) and didn't close
it.

It may help to re-run the specific test with `PYTHONTRACEMALLOC=25 pytest ...` so that
Python can display more of the stack trace where the connection was opened.
