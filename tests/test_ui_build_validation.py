from __future__ import annotations

import pathlib

import pytest
from hatch_build import (
    PACKAGED_UI_INDEX_FILES,
    REQUIRE_PACKAGED_UI_ENV_VAR,
    should_validate_packaged_ui_index_files,
    validate_packaged_ui_index_files,
)


def test_validate_packaged_ui_index_files_passes_when_both_indexes_exist(
    tmp_path: pathlib.Path,
):
    for index_file in PACKAGED_UI_INDEX_FILES:
        (tmp_path / index_file).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / index_file).write_text("<html></html>", encoding="utf-8")

    validate_packaged_ui_index_files(tmp_path)


def test_validate_packaged_ui_index_files_fails_when_an_index_is_missing(
    tmp_path: pathlib.Path,
):
    index_file = PACKAGED_UI_INDEX_FILES[0]
    (tmp_path / index_file).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / index_file).write_text("<html></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="src/prefect/server/ui-v2/index.html"):
        validate_packaged_ui_index_files(tmp_path)


def test_should_validate_packaged_ui_index_files_skips_plain_source_tree(
    tmp_path: pathlib.Path,
):
    assert not should_validate_packaged_ui_index_files(tmp_path)


def test_should_validate_packaged_ui_index_files_runs_when_required_by_env(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(REQUIRE_PACKAGED_UI_ENV_VAR, "1")

    assert should_validate_packaged_ui_index_files(tmp_path)


def test_should_validate_packaged_ui_index_files_runs_when_ui_bundle_dir_exists(
    tmp_path: pathlib.Path,
):
    (tmp_path / PACKAGED_UI_INDEX_FILES[0].parent).mkdir(parents=True)

    assert should_validate_packaged_ui_index_files(tmp_path)
