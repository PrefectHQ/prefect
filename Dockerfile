ARG PYTHON_VERSION=${PYTHON_VERSION:-3.8}
FROM python:${PYTHON_VERSION}-slim

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

LABEL maintainer="help@prefect.io"
LABEL io.prefect.python-version=${PYTHON_VERSION}
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="prefect"
LABEL org.label-schema.url="https://www.prefect.io/"

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        git=1:2.* \
        tini=0.19.* \
        # The following are required for building the asyncpg wheel
        gcc=4:10.* \
        linux-libc-dev=5.10.* \
        libc6-dev=2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Pin the pip version
RUN python -m pip install --no-cache-dir pip==21.3.1

# Copy the repository into the image
COPY . /opt/prefect

# Create an editable install
# In the future, we may want to install directly from git given a tag,
# but here we are optimizing for development
RUN pip install --no-cache-dir -e /opt/prefect

ENTRYPOINT ["tini", "-g", "--", "/opt/prefect/scripts/entrypoint.sh"]
