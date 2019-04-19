ARG GIT_POINTER=master
ARG PYTHON_VERSION=3.6

FROM python:${PYTHON_VERSION}
MAINTAINER tyler@prefect.io

RUN apt-get update && apt-get install -y graphviz
RUN pip install git+https://github.com/PrefectHQ/prefect.git@master#egg=prefect[kubernetes,viz]
RUN mkdir /root/.prefect/