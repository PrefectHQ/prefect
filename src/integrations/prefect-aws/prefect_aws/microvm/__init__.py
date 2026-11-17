"""
Entrypoint for running a Prefect flow run inside an AWS Lambda MicroVM.

Run `python -m prefect_aws.microvm` as the image's command. The process serves
the MicroVM lifecycle hooks, runs the flow run from the `/run` request in a
forked child process, and exits when the child does, which ends the MicroVM.
"""
