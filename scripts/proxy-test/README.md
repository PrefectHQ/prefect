This is a simple test to ensure we can make a websocket connection through a proxy server. It sets up a
simple server and a squid proxy server. The proxy server is inaccessible from the host machine, so we
can confirm the proxy connection is working.

```
$ uv pip install -r requirements.txt
$ docker compose up --build
$ python client.py
```
