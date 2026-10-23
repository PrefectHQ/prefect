"""Check the system, application, and installer trust stores in a built image."""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import ssl
import sys
from typing import Set

import certifi
from pip._vendor import certifi as pip_certifi

COMPROMISED_ROOTS = {
    "7dd78d5f4f13459a83dff9abbba62edbaf6f2d102bf257fd712f4d9f2746ed8d": "emSign Root TLS CA - G3",
    "f2edaaff3d9b701fb4d14c9f285f8c0bad90fc3bcc1fa07d47f4718edaba34a5": "emSign Root CS CA - G3",
    "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4": "AAA Certificate Services",
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b": "emSign ECC Root CA - G3",
}


def compromised_roots(context: ssl.SSLContext) -> Set[str]:
    """Return affected roots that the supplied TLS context actually trusts."""
    fingerprints = {
        hashlib.sha256(certificate).hexdigest()
        for certificate in context.get_ca_certs(binary_form=True)
    }
    return {
        COMPROMISED_ROOTS[digest] for digest in fingerprints & COMPROMISED_ROOTS.keys()
    }


def system_context() -> ssl.SSLContext:
    """Include hashed directory roots that OpenSSL otherwise loads lazily."""
    context = ssl.create_default_context()
    capath = ssl.get_default_verify_paths().capath
    for directory in capath.split(os.pathsep) if capath else []:
        for certificate in pathlib.Path(directory).iterdir():
            if re.fullmatch(r"[0-9a-fA-F]{8}\.\d+", certificate.name):
                context.load_verify_locations(cafile=str(certificate))
    return context


def main() -> int:
    """Fail the image build if any shipped default trust store is affected."""
    contexts = {
        "system": system_context(),
        "certifi": ssl.create_default_context(cafile=certifi.where()),
        "pip": ssl.create_default_context(cafile=pip_certifi.where()),
    }
    failed = False
    for name, context in contexts.items():
        roots = compromised_roots(context)
        if roots:
            print(f"{name} still trusts: {', '.join(sorted(roots))}", file=sys.stderr)
            failed = True
        else:
            print(f"{name}: affected CA roots are not trusted")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
