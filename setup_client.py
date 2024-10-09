import versioneer
from setuptools import find_packages, setup
from setuptools.command.egg_info import egg_info as _egg_info

install_requires = open("requirements-client.txt").read().strip().split("\n")

original_cmdclass = versioneer.get_cmdclass()


class CustomEggInfo(_egg_info):
    def tag_build(self):
        version = self.distribution.get_version()
        # Remove .dirty suffix if present
        if version.endswith(".dirty"):
            return version[:-6]
        return version


cmdclass = original_cmdclass.copy()
cmdclass.update({"egg_info": CustomEggInfo})

setup(
    # Package metadata
    name="prefect-client",
    description="Workflow orchestration and management.",
    author="Prefect Technologies, Inc.",
    author_email="help@prefect.io",
    url="https://www.prefect.io",
    project_urls={
        "Changelog": "https://github.com/PrefectHQ/prefect/releases",
        "Documentation": "https://docs.prefect.io",
        "Source": "https://github.com/PrefectHQ/prefect",
        "Tracker": "https://github.com/PrefectHQ/prefect/issues",
    },
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    # Versioning
    version=versioneer.get_version(),
    cmdclass=cmdclass,
    # Package setup
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    # Requirements
    python_requires=">=3.9",
    install_requires=install_requires,
    extras_require={"notifications": ["apprise>=1.1.0, <2.0.0"]},
    classifiers=[
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
    ],
)
