from datetime import timedelta

from prefect import flow
from prefect.automations import (
    Automation,
    EventTrigger,
    Posture,
    ResourceSpecification,
    RunDeployment,
)
from prefect.docker import DockerImage


@flow
def alpha(name: str, value: int):
    print(name, value)


@flow
def beta(name: str, value: int, another: float):
    print(name, value, another)


if __name__ == "__main__":
    # Note: deploy these flows in the way you best see fit for your environment
    alpha.deploy(
        name="alpha",
        work_pool_name="my-docker-work-pool",
        image=DockerImage(
            name="localhost:5000/my_image",
            dockerfile="Dockerfile",
        ),
        push=False,
    )
    beta_deployment_id = beta.deploy(
        name="beta",
        work_pool_name="my-docker-work-pool",
        image=DockerImage(
            name="localhost:5000/my_image",
            dockerfile="Dockerfile",
        ),
        push=False,
    )

    automation = Automation(
        name="Passing parameters",
        trigger=EventTrigger(
            # Here we're matching on every completion of the `alpha` flow
            expect={"prefect.flow-run.Completed"},
            match_related=ResourceSpecification(
                {"prefect.resource.role": "flow", "prefect.resource.name": "alpha"}
            ),
            # And we'll react to each event immediately and individually
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(0),
        ),
        actions=[
            RunDeployment(
                # We will be selecting a specific deployment (rather than attempting to
                # infer it from the event)
                source="selected",
                # The deployment we want to run is the `beta` deployment we created above
                deployment_id=beta_deployment_id,
                parameters={
                    # For the "name" and "value" parameters, we tell Prefect we're using a
                    # Jinja2 template by creating a nested dictionary with the special
                    # `__prefect_kind` key set to "jinja".  Then we supply the `template`
                    # value with any valid Jinja2 template.  This step may also be done
                    # in the Prefect UI by selecting "Use Jinja input" for the parameters
                    # you want to template.
                    #
                    # The "{{ flow_run }}" variable here is a special shortcut that gives us
                    # access to the `FlowRun` object associated with this event.  There are
                    # also variables like "{{ deployment }}", "{{ flow }}",
                    # "{{ work_pool }}" and so on.
                    #
                    # In this case, the {{ flow_run }} represent the run of `alpha` that
                    # emitted the `prefect.flow-run.Completed` event that triggered this
                    # automation.
                    "name": {
                        "template": "{{ flow_run.parameters['name'] }}",
                        "__prefect_kind": "jinja",
                    },
                    "value": {
                        "template": "{{ flow_run.parameters['value'] }}",
                        "__prefect_kind": "jinja",
                    },
                    # You can also just pass literal parameters
                    "another": 1.2345,
                },
            )
        ],
    ).create()
