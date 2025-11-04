#!/usr/bin/env bash


#!/usr/bin/env bash

set -e

PROTO_ROOT="${PROTO_ROOT:-..}"


# https://buf.build/docs/installation

cp $PROTO_ROOT/prefab-cloud/prefab.proto .
buf generate
