```docker
FROM prefecthq/prefect:2-python3.9
RUN pip install s3fs prefect-aws
```