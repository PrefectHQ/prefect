import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from prefect._internal.installation import ainstall_packages, install_packages


class TestInstallPackages:
    @patch("prefect._internal.installation.importlib.import_module")
    @patch("subprocess.check_call")
    def test_install_packages_with_uv_available(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        install_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @patch(
        "prefect._internal.installation.importlib.import_module",
        side_effect=ImportError("No module named 'uv'"),
    )
    @patch("subprocess.check_call")
    def test_install_packages_with_uv_unavailable_import_error(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]

        install_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @patch(
        "prefect._internal.installation.importlib.import_module",
        side_effect=ModuleNotFoundError("No module named 'uv'"),
    )
    @patch("subprocess.check_call")
    def test_install_packages_with_uv_unavailable_module_not_found_error(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]

        install_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("subprocess.check_call")
    def test_install_packages_with_uv_file_not_found_error(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.side_effect = FileNotFoundError
        mock_import_module.return_value = mock_uv

        install_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("subprocess.check_call")
    def test_install_packages_with_upgrade_flag(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        install_packages(packages, upgrade=True)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests", "--upgrade"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("subprocess.check_call")
    def test_install_packages_with_stream_output(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        install_packages(packages, stream_output=True)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("subprocess.check_call")
    def test_install_packages_with_upgrade_and_stream_output(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        install_packages(packages, stream_output=True, upgrade=True)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests", "--upgrade"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    @patch(
        "prefect._internal.installation.importlib.import_module",
        side_effect=ImportError("No module named 'uv'"),
    )
    @patch("subprocess.check_call")
    def test_install_packages_fallback_with_upgrade_and_stream_output(
        self, mock_check_call: MagicMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]

        install_packages(packages, stream_output=True, upgrade=True)

        mock_import_module.assert_called_once_with("uv")
        mock_check_call.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests", "--upgrade"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )


class TestAinstallPackages:
    @patch("prefect._internal.installation.importlib.import_module")
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_with_uv_available(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        await ainstall_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests"],
            stream_output=False,
        )

    @patch(
        "prefect._internal.installation.importlib.import_module",
        side_effect=ImportError("No module named 'uv'"),
    )
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_with_uv_unavailable_import_error(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]

        await ainstall_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests"],
            stream_output=False,
        )

    @patch(
        "prefect._internal.installation.importlib.import_module",
        side_effect=ModuleNotFoundError("No module named 'uv'"),
    )
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_with_uv_unavailable_module_not_found_error(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]

        await ainstall_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests"],
            stream_output=False,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_with_uv_file_not_found_error(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.side_effect = FileNotFoundError
        mock_import_module.return_value = mock_uv

        await ainstall_packages(packages)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests"],
            stream_output=False,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_with_upgrade_flag(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        await ainstall_packages(packages, upgrade=True)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests", "--upgrade"],
            stream_output=False,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_with_stream_output(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        await ainstall_packages(packages, stream_output=True)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests"],
            stream_output=True,
        )

    @patch("prefect._internal.installation.importlib.import_module")
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_with_upgrade_and_stream_output(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]
        mock_uv = Mock()
        mock_uv.find_uv_bin.return_value = "/path/to/uv"
        mock_import_module.return_value = mock_uv

        await ainstall_packages(packages, stream_output=True, upgrade=True)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            ["/path/to/uv", "pip", "install", "pytest", "requests", "--upgrade"],
            stream_output=True,
        )

    @patch(
        "prefect._internal.installation.importlib.import_module",
        side_effect=ImportError("No module named 'uv'"),
    )
    @patch("prefect.utilities.processutils.run_process", new_callable=AsyncMock)
    async def test_ainstall_packages_fallback_with_upgrade_and_stream_output(
        self, mock_run_process: AsyncMock, mock_import_module: MagicMock
    ):
        packages = ["pytest", "requests"]

        await ainstall_packages(packages, stream_output=True, upgrade=True)

        mock_import_module.assert_called_once_with("uv")
        mock_run_process.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "pytest", "requests", "--upgrade"],
            stream_output=True,
        )
