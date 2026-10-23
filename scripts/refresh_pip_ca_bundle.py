"""Refresh legacy pip's vendored trust store from the installed certifi bundle."""

import shutil

import certifi
from pip._vendor import certifi as pip_certifi

shutil.copyfile(certifi.where(), pip_certifi.where())
