import pytest
from prefect.docker import parse_image_tag
from itertools import product

image_names = ['some_url_to_a_docker_repo.com:5050/path/to/image','some_url_to_a_docker_repo.com/path/to/image']
image_tags = [[], ['tag1']]
@pytest.mark.parametrize('docker_image,image_name,image_tag', [(':'.join([image]+tag), image, tag) for image, tag in product(image_names, image_tags)])
def test_docker_image_parsing(docker_image,image_name,image_tag):
    parsed_image, parsed_tag = parse_image_tag(docker_image)
    assert parsed_image == image
    assert parsed_tag == (image_tag[0] if len(image_tag)>0 else None)

