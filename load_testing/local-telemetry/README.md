# local-telemetry

This directory includes an OpenTelemetry stack that you can run locally for testing and debugging.

## Quickstart

```bash
$ ./local-telemetry/start
```

This will start the local OpenTelemetry stack in the background.  Several services
will be running:

* Jaeger is a frontend for viewing traces, and will be available at http://localhost:16686
* Prometheus captures metrics, and exposes a frontend at http://localhost:9090

Then, run your local server according to the instructions in the [load_testing/README.md](../README.md) file.

When making requests against your local server, you'll see trace appearing in the
Jaeger frontend at `http://localhost:16686`.
