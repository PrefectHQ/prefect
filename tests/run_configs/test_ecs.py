from prefect.run_configs import ECSRun


def test_no_args():
    config = ECSRun()
    assert config.task_definition is None
    assert config.image is None
    assert config.env is None
    assert config.cpu is None
    assert config.memory is None
    assert config.run_task_kwargs is None
    assert config.labels == set()


def test_all_args():
    config = ECSRun(
        task_definition="my-definition",
        image="myimage",
        env={"HELLO": "WORLD"},
        cpu=1024,
        memory=2048,
        run_task_kwargs={"overrides": {"taskRoleArn": "example"}},
        labels=["a", "b"],
    )
    assert config.task_definition == "my-definition"
    assert config.image == "myimage"
    assert config.env == {"HELLO": "WORLD"}
    assert config.cpu == "1024"
    assert config.memory == "2048"
    assert config.run_task_kwargs == {"overrides": {"taskRoleArn": "example"}}
    assert config.labels == {"a", "b"}


def test_labels():
    config = ECSRun(labels=["a", "b"])
    assert config.labels == {"a", "b"}


def test_cpu_and_memory_acceptable_types():
    config = ECSRun()
    assert config.cpu is None
    assert config.memory is None

    config = ECSRun(cpu="1 vcpu", memory="1 GB")
    assert config.cpu == "1 vcpu"
    assert config.memory == "1 GB"

    config = ECSRun(cpu=1024, memory=2048)
    assert config.cpu == "1024"
    assert config.memory == "2048"
