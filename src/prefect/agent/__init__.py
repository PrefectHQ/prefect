# only agents that don't require `extras` should be automatically imported here;
# others must be explicitly imported so they can raise helpful errors if appropriate

from prefect.agent.agent import Agent
import prefect.agent.docker
import prefect.agent.fargate
import prefect.agent.kubernetes
import prefect.agent.local
import prefect.agent.ecs
