from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _dockerfile_lines(path: str) -> list[str]:
    return (REPO_ROOT / path).read_text(encoding="utf-8").splitlines()


def test_prefect_image_does_not_export_uv_compile_bytecode():
    lines = _dockerfile_lines("Dockerfile")

    assert "ENV UV_COMPILE_BYTECODE=1" not in lines
    assert any("UV_COMPILE_BYTECODE=1 uv pip install" in line for line in lines), (
        "expected bytecode compilation to remain scoped to build-time installs"
    )


def test_prefect_client_image_does_not_export_uv_compile_bytecode():
    lines = _dockerfile_lines("client/Dockerfile")

    assert "ENV UV_COMPILE_BYTECODE=1" not in lines
    assert any("UV_COMPILE_BYTECODE=1 uv pip install" in line for line in lines), (
        "expected bytecode compilation to remain scoped to build-time installs"
    )
