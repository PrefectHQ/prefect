#!/usr/bin/env bash

set -e 

VERSION=${VERSION}
ARCH=$(uname -m)
REPO="brigad/irdu-data/prefect/production"
ACCOUNT="227743832892.dkr.ecr.eu-west-1.amazonaws.com"
FULL_REPO="${ACCOUNT}/${REPO}"

echo $FULL_REPO

docker build --build-arg PYTHON_VERSION=3.11 --build-arg BUILD_PYTHON_VERSION=3.11 -f ../Dockerfile .. -t ${FULL_REPO}:${VERSION}-${ARCH}

docker push ${FULL_REPO}:${VERSION}-${ARCH}

IMAGES=$(aws ecr list-images --repository-name ${REPO} |jq -c '.imageIds[] | select(has("imageTag") and (.imageTag | contains("2.11.4-"))) | .imageTag' | xargs -I% echo ${FULL_REPO}:% | xargs)

echo ${IMAGES}

docker manifest create ${FULL_REPO}:${VERSION} ${IMAGES} --amend 

docker manifest push ${FULL_REPO}:${VERSION}
