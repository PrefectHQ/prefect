{
    "Job": {
        "ID": "prefect-job-UUID",
        "Name": "prefect-job-UUID",
        "Type": "batch",
        "Datacenters": [
            "dc1"
        ],
        "TaskGroups": [{
            "Name": "flow",
            "Count": 1,
            "Tasks": [{
                "Name": "flow",
                "Driver": "docker",
                "Env": {
                    "PREFECT__CLOUD__API": "XX",
                    "PREFECT__CLOUD__AUTH_TOKEN": "XX",
                    "PREFECT__CONTEXT__FLOW_RUN_ID": "XX",
                    "PREFECT__CONTEXT__NAMESPACE": "XX",
                    "PREFECT__LOGGING__LOG_TO_CLOUD": "XX",
                    "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                    "PREFECT__LOGGING__LEVEL": "DEBUG",
                    "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                    "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner"
                },
                "Config": {
                    "image": "prefecthq/prefect:latest",
                    "command": "/bin/bash",
                    "args": ["-c", "prefect execute cloud-flow"]
                },
                "Resources": {
                    "CPU": 100
                }
            }],
            "RestartPolicy": {
                "Attempts": 0
            }
        }]
    }
}
