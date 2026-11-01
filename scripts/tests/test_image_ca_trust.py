"""Exercise the image trust check against the published incident chains."""

import importlib.util
import os
import pathlib
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest

import certifi
import pip
from pip._vendor import certifi as pip_certifi

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).with_name("tls")
SPEC = importlib.util.spec_from_file_location(
    "check_image_ca_trust", ROOT / "scripts" / "check_image_ca_trust.py"
)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class ImageTrustTests(unittest.TestCase):
    def run_check(self, bundle, directory):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_image_ca_trust.py")],
            env={
                **os.environ,
                "SSL_CERT_FILE": str(bundle),
                "SSL_CERT_DIR": str(directory),
            },
            capture_output=True,
            text=True,
            check=False,
        )

    def test_detects_actual_compromised_trust_anchors(self):
        context = ssl.create_default_context(
            cafile=str(FIXTURES / "compromised-roots.pem")
        )
        self.assertEqual(
            CHECK.compromised_roots(context),
            {
                "emSign Root TLS CA - G3",
                "emSign Root CS CA - G3",
                "AAA Certificate Services",
                "emSign ECC Root CA - G3",
            },
        )

    def test_accepts_patched_certifi_bundle(self):
        context = ssl.create_default_context(cafile=certifi.where())
        self.assertEqual(CHECK.compromised_roots(context), set())

    def test_cli_rejects_compromised_system_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_check(FIXTURES / "compromised-roots.pem", directory)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("system still trusts", result.stderr)

    def test_cli_accepts_patched_stores(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_check(certifi.where(), directory)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_rejects_compromised_application_and_installer_bundles(self):
        for name, module, bundle in [
            ("certifi", certifi, certifi.where()),
            ("pip", pip, pip_certifi.where()),
        ]:
            with self.subTest(store=name), tempfile.TemporaryDirectory() as directory:
                source = pathlib.Path(module.__file__).parent
                package = pathlib.Path(directory, name)
                shutil.copytree(source, package)
                shutil.copyfile(
                    FIXTURES / "compromised-roots.pem",
                    package / pathlib.Path(bundle).relative_to(source),
                )
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/check_image_ca_trust.py")],
                    env={
                        **os.environ,
                        "PYTHONPATH": directory,
                        "SSL_CERT_FILE": certifi.where(),
                        "SSL_CERT_DIR": directory,
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(name + " still trusts", result.stderr)

    def test_cli_rejects_lazily_loaded_directory_roots(self):
        digest = subprocess.check_output(
            [
                "openssl",
                "x509",
                "-hash",
                "-noout",
                "-in",
                str(FIXTURES / "compromised-roots.pem"),
            ],
            text=True,
        ).strip()
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, digest + ".0").write_bytes(
                (FIXTURES / "compromised-roots.pem").read_bytes()
            )
            result = self.run_check(certifi.where(), directory)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("system still trusts", result.stderr)

    def test_incident_chains_verify_only_with_compromised_roots(self):
        for chain in sorted(FIXTURES.glob("*-emudhra.we-have-a-problem.com.pem")):
            for bundle, expected in [
                (str(FIXTURES / "compromised-roots.pem"), 0),
                (certifi.where(), 2),
            ]:
                with self.subTest(chain=chain.name, bundle=bundle):
                    result = subprocess.run(
                        [
                            "openssl",
                            "verify",
                            "-attime",
                            "1792540800",
                            "-purpose",
                            "sslserver",
                            "-verify_hostname",
                            chain.stem,
                            "-trusted",
                            bundle,
                            "-untrusted",
                            str(chain),
                            str(chain),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(
                        result.returncode, expected, result.stdout + result.stderr
                    )
                    if expected:
                        self.assertIn("unable to get local issuer", result.stderr)


if __name__ == "__main__":
    unittest.main()
