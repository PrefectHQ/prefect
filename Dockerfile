ARG PYTHON_VERSION=${PYTHON_VERSION:-3.6}
FROM python:${PYTHON_VERSION}-slim

RUN apt update && apt install -y gcc git && rm -rf /var/lib/apt/lists/*

ARG PREFECT_VERSION
RUN pip install git+https://github.com/PrefectHQ/prefect.git@${PREFECT_VERSION}#egg=prefect[kubernetes]
RUN mkdir /root/.prefect/

ARG GIT_SHA
ARG BUILD_DATE

LABEL maintainer="help@prefect.io"
LABEL io.prefect.python-version=${PYTHON_VERSION}
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="prefect"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_VERSION}
LABEL org.label-schema.vcs-ref=${GIT_SHA}
LABEL org.label-schema.build-date=${BUILD_DATE}