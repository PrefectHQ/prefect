import pytest
from prefect.docker import parse_image_tag
from itertools import product

@pytest.mark.parametrize('docker_image,expected_image_name,expected_image_tag', [
    ('some_url_to_a_docker_repo.com:5050/path/to/image','some_url_to_a_docker_repo.com:5050/path/to/image', None),
    ('some_url_to_a_docker_repo.com:5050/path/to/image:tag1','some_url_to_a_docker_repo.com:5050/path/to/image', 'tag1'),
    ('some_url_to_a_docker_repo.com/path/to/image','some_url_to_a_docker_repo.com/path/to/image', None),
    ('some_url_to_a_docker_repo.com/path/to/image:tag1','some_url_to_a_docker_repo.com/path/to/image', 'tag1'),
    ('path/to/image','path/to/image', None),
    ('path/to/image:tag1','path/to/image', 'tag1'),
    ])
def test_docker_image_parsing(docker_image,expected_image_name,expected_image_tag):
    parsed_image, parsed_tag = parse_image_tag(docker_image)
    assert parsed_image == expected_image_name
    assert parsed_tag == expected_image_tag

@pytest.mark.parametrize('docker_image', [
    'http://some_url_to_a_docker_repo.com/path/to/image',
    'https://some_url_to_a_docker_repo.com/path/to/image',
    'some_url_to_a_docker_repo.com:5050/path/to/image:tag1:tag2',
    'some_url_to_a_docker_repo.com/path/to/image:tag1:tag2',
    ])
def test_docker_image_parsing_value_error(docker_image):
    with pytest.raises(ValueError):
        parse_image_tag(docker_image)
