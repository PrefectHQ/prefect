
FROM python:3.6

# Private repo prevents us from easily using alpine based images

ARG PERSONAL_ACCESS_TOKEN
ENV PERSONAL_ACCESS_TOKEN=$PERSONAL_ACCESS_TOKEN

RUN git clone -b dask https://$PERSONAL_ACCESS_TOKEN@github.com/PrefectHQ/prefect.git

RUN pip install ./prefect

RUN mkdir /root/.prefect/