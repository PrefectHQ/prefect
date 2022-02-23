# Common mistakes

## API tests return an unexpected 307 Redirected

HTTPX disabled redirect following by default in [`0.22.0`](https://github.com/encode/httpx/blob/master/CHANGELOG.md#0200-13th-october-2021).

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
