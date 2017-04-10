from setuptools import setup, find_packages

install_requires = [
    'click',
    'croniter',
    'pyjwt',
    'pycrypto',
    'transitions',
    'ujson',
]

extras = {
    # 's3': ['awsfs'],
    # 'gcs': ['https://github.com/martindurant/gcsfs.git'],
    'test': ['pytest', 'pytest-env', 'pytest-xdist'],
}

setup(
    name='prefect',
    version='0.0',
    description='',
    long_description=open('README.md').read(),
    url='https://gitlab.com/prefect/prefect',
    author='jlowin',
    author_email='jlowin@apache.org',
    install_requires=install_requires,
    extras_require=extras,
    scripts=[],
    packages=find_packages(),
    include_package_data=True,
    entry_points={'console_scripts': [
        'prefect=prefect.cli:cli',
    ]})
