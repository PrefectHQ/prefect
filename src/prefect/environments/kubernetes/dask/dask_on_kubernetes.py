
class DaskOnKubernetesEnvironment(DockerEnvironment):

    def __init__(
        self,
        base_image: str = "python:3.6",
        registry_url: str = None,
        python_dependencies: list = None,
        image_name: str = None,
        image_tag: str = None,
        env_vars: dict = None,
        files: dict = None,
    ) -> None:
        super().__init__(
            base_image=base_image,
            registry_url=registry_url,
            python_dependencies=python_dependencies,
            image_name=image_name,
            image_tag=image_tag,
            env_vars=env_vars,
            files=files,
        )

        self.identifier_label = str(uuid.uuid4())