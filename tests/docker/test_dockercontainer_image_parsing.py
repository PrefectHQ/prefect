from prefect.infrastructure.docker import DockerContainer

def docker_image_parsing(image, tags):
    d = DockerContainer(image=':'.join([image]+tags))
    parsed_image, parsed_tag = d._get_image_and_tag()
    assert parsed_image == image
    assert parsed_tag == tags[0]

def test_dockercontainer_image_parsing():
    for image in ['some_url_to_a_docker_repo.com:5050/path/to/image','some_url_to_a_docker_repo.com/path/to/image']:
        for tags in [[],['tag1'],['tag1','tag2']]:
            docker_image_parsing(image, tags)
