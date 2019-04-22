ARG GIT_POINTER=master
ARG PYTHON_VERSION=3.6

FROM python:${PYTHON_VERSION}
MAINTAINER help@prefect.io

RUN pip install git+https://github.com/PrefectHQ/prefect.git@master#egg=prefect[kubernetes]
RUN mkdir /root/.prefect/