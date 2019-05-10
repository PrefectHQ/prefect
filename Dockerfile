ARG PYTHON_VERSION=3.6

FROM python:${PYTHON_VERSION}
LABEL maintainer="help@prefect.io"
ARG GIT_POINTER=master

RUN pip install git+https://github.com/PrefectHQ/prefect.git@${GIT_POINTER}#egg=prefect[kubernetes]
RUN mkdir /root/.prefect/
