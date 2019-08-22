job "prefect-agent" {
  # region = "global"

  datacenters = ["dc1"]
#  datacenters = ["us-east-1"]

  type = "service"

 # eventually we might consider placing the resource manager in this group as well
  group "prefect" {
    count = 1

    restart {
      attempts = 5
      delay = "5s"
      interval = "30s"
      mode = "fail"
    }

    task "agent" {
      # The "driver" parameter specifies the task driver that should be used to
      # run the task.
      driver = "docker"

      # config for docker
      config {
        image = "IMAGE"
        command = "/bin/bash"
        args = ["-c", "prefect agent start nomad-agent"]
        force_pull = true
      }

      env {
        NOMAD_HOST = "http://127.0.0.1:4646"
        PREFECT__CLOUD__AGENT__AUTH_TOKEN = "TOKEN"
        PREFECT__CLOUD__API = "https://api.prefect.io"
        NAMESPACE = "default"
      }

      resources {
        cpu    = 200
        memory = 128
      }

    }
  }
}
