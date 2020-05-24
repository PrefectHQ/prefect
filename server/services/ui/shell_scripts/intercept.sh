#!/usr/bin/env bash

function _intercept {
    kill -TERM $child
    exit 0
}

trap _intercept SIGTERM
trap _intercept SIGINT
trap _intercept SIGQUIT
trap _intercept EXIT

/start_server.sh & tail -f /dev/null & child=$!

wait "$child"