"""
Tests for FileCollector single file collection.

This module tests the FileCollector class's ability to collect single files
by pattern. Tests cover:
- Collecting existing single files
- Handling non-existent files (warning, no error)
- Directory traversal protection
- CollectionResult dataclass behavior
"""

from __future__ import annotations

import platform

import pytest

from prefect._experimental.bundles._file_collector import (
    CollectionResult,
    FileCollector,
)
from prefect._experimental.bundles._path_resolver import PathValidationError


class TestCollectionResult:
    """Tests for CollectionResult dataclass."""

    def test_create_empty_result(self):
        """Test creating an empty CollectionResult."""
        result = CollectionResult()
        assert result.files == []
        assert result.warnings == []
        assert result.total_size == 0
        assert result.patterns_matched == {}

    def test_create_with_files(self, tmp_path):
        """Test creating a CollectionResult with files."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.touch()
        file2.touch()

        result = CollectionResult(
            files=[file1, file2],
            warnings=[],
            total_size=0,
            patterns_matched={"a.txt": [file1], "b.txt": [file2]},
        )
        assert len(result.files) == 2
        assert file1 in result.files
        assert file2 in result.files

    def test_create_with_warnings(self):
        """Test creating a CollectionResult with warnings."""
        result = CollectionResult(
            files=[],
            warnings=["Pattern 'missing.txt' matched no files"],
            total_size=0,
            patterns_matched={"missing.txt": []},
        )
        assert len(result.warnings) == 1
        assert "missing.txt" in result.warnings[0]

    def test_total_size_tracking(self, tmp_path):
        """Test that total_size is tracked correctly."""
        file = tmp_path / "data.txt"
        file.write_text("12345")  # 5 bytes

        result = CollectionResult(
            files=[file],
            warnings=[],
            total_size=5,
            patterns_matched={"data.txt": [file]},
        )
        assert result.total_size == 5

    def test_patterns_matched_tracking(self, tmp_path):
        """Test patterns_matched tracks which files each pattern matched."""
        file = tmp_path / "config.yaml"
        file.touch()

        result = CollectionResult(
            files=[file],
            warnings=[],
            total_size=0,
            patterns_matched={"config.yaml": [file]},
        )
        assert "config.yaml" in result.patterns_matched
        assert result.patterns_matched["config.yaml"] == [file]


class TestFileCollector:
    """Tests for FileCollector class."""

    def test_init_with_base_dir(self, tmp_path):
        """Test FileCollector initializes with base directory."""
        collector = FileCollector(tmp_path)
        assert collector.base_dir == tmp_path.resolve()

    def test_collect_single_existing_file(self, tmp_path):
        """Test collecting a single existing file."""
        # Setup: create a config file
        config = tmp_path / "config.yaml"
        config.write_text("key: value")

        # Collect the file
        collector = FileCollector(tmp_path)
        result = collector.collect(["config.yaml"])

        # Verify
        assert len(result.files) == 1
        assert result.files[0] == config.resolve()
        assert result.warnings == []
        assert "config.yaml" in result.patterns_matched
        assert result.patterns_matched["config.yaml"] == [config.resolve()]

    def test_collect_single_file_tracks_size(self, tmp_path):
        """Test that file size is tracked in total_size."""
        # Setup: create file with known content
        data_file = tmp_path / "data.txt"
        data_file.write_text("hello world")  # 11 bytes

        collector = FileCollector(tmp_path)
        result = collector.collect(["data.txt"])

        assert result.total_size == 11

    def test_collect_missing_file_adds_warning(self, tmp_path):
        """Test that missing file adds warning instead of raising."""
        collector = FileCollector(tmp_path)
        result = collector.collect(["nonexistent.txt"])

        # Should have warning, not raise
        assert len(result.files) == 0
        assert len(result.warnings) == 1
        assert "nonexistent.txt" in result.warnings[0]
        assert "matched no files" in result.warnings[0].lower()
        # Pattern should be tracked with empty match list
        assert result.patterns_matched["nonexistent.txt"] == []

    def test_collect_multiple_files(self, tmp_path):
        """Test collecting multiple single files."""
        # Setup: create multiple files
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("aaa")
        file2.write_text("bbbbb")

        collector = FileCollector(tmp_path)
        result = collector.collect(["a.txt", "b.txt"])

        assert len(result.files) == 2
        assert file1.resolve() in result.files
        assert file2.resolve() in result.files
        assert result.total_size == 8  # 3 + 5

    def test_collect_mix_of_existing_and_missing(self, tmp_path):
        """Test collecting mix of existing and missing files."""
        # Setup: only create one file
        existing = tmp_path / "exists.txt"
        existing.write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["exists.txt", "missing.txt"])

        # Should have one file and one warning
        assert len(result.files) == 1
        assert existing.resolve() in result.files
        assert len(result.warnings) == 1
        assert "missing.txt" in result.warnings[0]

    def test_collect_file_in_subdirectory(self, tmp_path):
        """Test collecting a file in a subdirectory."""
        # Setup: create nested file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        nested_file = data_dir / "input.csv"
        nested_file.write_text("col1,col2")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/input.csv"])

        assert len(result.files) == 1
        assert result.files[0] == nested_file.resolve()

    def test_collect_traversal_raises_error(self, tmp_path):
        """Test that directory traversal raises PathValidationError."""
        collector = FileCollector(tmp_path)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["../escape.txt"])

        assert exc_info.value.error_type == "traversal"

    def test_collect_multiple_traversals_raises_on_first(self, tmp_path):
        """Test that traversal is caught even with valid files."""
        # Setup: create a valid file
        valid = tmp_path / "valid.txt"
        valid.touch()

        collector = FileCollector(tmp_path)

        # Traversal pattern first should raise immediately
        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["../escape.txt", "valid.txt"])

        assert exc_info.value.error_type == "traversal"

    def test_collect_absolute_path_raises_error(self, tmp_path):
        """Test that absolute paths raise PathValidationError."""
        collector = FileCollector(tmp_path)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["/etc/passwd"])

        assert exc_info.value.error_type == "absolute"

    def test_collect_empty_pattern_raises_error(self, tmp_path):
        """Test that empty pattern raises PathValidationError."""
        collector = FileCollector(tmp_path)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect([""])

        assert exc_info.value.error_type == "empty"

    def test_collect_dotfile(self, tmp_path):
        """Test collecting a dotfile."""
        dotfile = tmp_path / ".gitignore"
        dotfile.write_text("*.pyc")

        collector = FileCollector(tmp_path)
        result = collector.collect([".gitignore"])

        assert len(result.files) == 1
        assert result.files[0] == dotfile.resolve()

    def test_collect_file_with_backslash_path(self, tmp_path):
        """Test collecting file with Windows-style backslash path."""
        # Setup: create nested file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        nested_file = data_dir / "file.txt"
        nested_file.write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data\\file.txt"])

        assert len(result.files) == 1
        assert result.files[0] == nested_file.resolve()

    def test_collect_empty_list(self, tmp_path):
        """Test collecting with empty pattern list."""
        collector = FileCollector(tmp_path)
        result = collector.collect([])

        assert result.files == []
        assert result.warnings == []
        assert result.total_size == 0
        assert result.patterns_matched == {}


# Skip symlink tests on Windows since symlink creation requires admin privileges
symlink_skip = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Symlink tests require admin privileges on Windows",
)


@symlink_skip
class TestFileCollectorSymlinks:
    """Tests for FileCollector symlink handling."""

    def test_collect_symlink_within_base_dir(self, tmp_path):
        """Test collecting a symlink that points within base dir."""
        # Setup: create target and symlink
        target = tmp_path / "actual.txt"
        target.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        collector = FileCollector(tmp_path)
        result = collector.collect(["link.txt"])

        # Should resolve to the target file
        assert len(result.files) == 1
        assert result.files[0] == target.resolve()

    def test_collect_symlink_escaping_base_dir_raises(self, tmp_path):
        """Test that symlink escaping base dir raises PathValidationError."""
        # Setup: create target outside base and symlink inside
        base_dir = tmp_path / "project"
        base_dir.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        link = base_dir / "sneaky.txt"
        link.symlink_to(outside)

        collector = FileCollector(base_dir)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["sneaky.txt"])

        assert exc_info.value.error_type == "traversal"

    def test_collect_broken_symlink_adds_warning(self, tmp_path):
        """Test that broken symlink adds warning instead of raising."""
        # Setup: create a symlink to nonexistent target
        link = tmp_path / "broken.txt"
        link.symlink_to(tmp_path / "nonexistent.txt")

        collector = FileCollector(tmp_path)
        result = collector.collect(["broken.txt"])

        # Should be treated as missing file
        assert len(result.files) == 0
        assert len(result.warnings) == 1
        assert "broken.txt" in result.warnings[0]


class TestFileCollectorDirectory:
    """Tests for FileCollector directory collection."""

    def test_collect_directory_gets_all_files(self, tmp_path):
        """Test collecting directory gets all files recursively."""
        # Setup: create directory with files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "a.txt").write_text("aaa")
        (data_dir / "b.txt").write_text("bbb")
        subdir = data_dir / "sub"
        subdir.mkdir()
        (subdir / "c.txt").write_text("ccc")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # Should collect all 3 files
        assert len(result.files) == 3
        assert result.total_size == 9  # 3 + 3 + 3

    def test_collect_directory_without_trailing_slash(self, tmp_path):
        """Test that directory pattern works without trailing slash."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data"])

        assert len(result.files) == 1

    def test_collect_directory_excludes_hidden_files(self, tmp_path):
        """Test that hidden files (dotfiles) are excluded by default."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "visible.txt").write_text("visible")
        (data_dir / ".hidden").write_text("hidden")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # Only visible file should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "visible.txt"

    def test_collect_directory_excludes_hidden_directories(self, tmp_path):
        """Test that files in hidden directories are excluded."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "visible.txt").write_text("visible")
        hidden_dir = data_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.txt").write_text("secret")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # Only visible file should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "visible.txt"

    def test_collect_directory_excludes_pycache(self, tmp_path):
        """Test that __pycache__ directories are excluded."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "module.py").write_text("# code")
        pycache = data_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "module.cpython-311.pyc").write_bytes(b"\x00\x00")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # Only module.py should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "module.py"

    def test_collect_directory_excludes_pyc_files(self, tmp_path):
        """Test that .pyc files are excluded even outside __pycache__."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "module.py").write_text("# code")
        (data_dir / "old.pyc").write_bytes(b"\x00\x00")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # Only module.py should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "module.py"

    def test_collect_directory_excludes_node_modules(self, tmp_path):
        """Test that node_modules directories are excluded."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "index.js").write_text("// code")
        node_modules = project_dir / "node_modules"
        node_modules.mkdir()
        dep = node_modules / "some-dep"
        dep.mkdir()
        (dep / "index.js").write_text("// dep")

        collector = FileCollector(tmp_path)
        result = collector.collect(["project/"])

        # Only project index.js should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "index.js"

    def test_collect_directory_excludes_venv(self, tmp_path):
        """Test that venv and .venv directories are excluded."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("# code")
        venv = project_dir / "venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr")
        dotvenv = project_dir / ".venv"
        dotvenv.mkdir()
        (dotvenv / "pyvenv.cfg").write_text("home = /usr")

        collector = FileCollector(tmp_path)
        result = collector.collect(["project/"])

        # Only main.py should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "main.py"

    def test_collect_directory_excludes_ide_directories(self, tmp_path):
        """Test that .idea and .vscode directories are excluded."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("# code")
        idea = project_dir / ".idea"
        idea.mkdir()
        (idea / "workspace.xml").write_text("<xml>")
        vscode = project_dir / ".vscode"
        vscode.mkdir()
        (vscode / "settings.json").write_text("{}")

        collector = FileCollector(tmp_path)
        result = collector.collect(["project/"])

        # Only main.py should be collected (IDE dirs are hidden anyway)
        assert len(result.files) == 1
        assert result.files[0].name == "main.py"

    def test_collect_empty_directory_adds_warning(self, tmp_path):
        """Test that empty directory produces warning, not error."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        collector = FileCollector(tmp_path)
        result = collector.collect(["empty/"])

        assert len(result.files) == 0
        assert len(result.warnings) == 1
        assert "empty" in result.warnings[0].lower()

    def test_collect_directory_with_only_hidden_files_adds_warning(self, tmp_path):
        """Test directory with only hidden files produces warning."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / ".hidden1").write_text("hidden")
        (data_dir / ".hidden2").write_text("hidden")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # All files excluded, should warn
        assert len(result.files) == 0
        assert len(result.warnings) == 1

    def test_collect_directory_tracks_pattern(self, tmp_path):
        """Test that directory pattern is tracked in patterns_matched."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "a.txt").write_text("a")
        (data_dir / "b.txt").write_text("b")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        assert "data/" in result.patterns_matched
        assert len(result.patterns_matched["data/"]) == 2

    def test_collect_directory_excludes_egg_info(self, tmp_path):
        """Test that *.egg-info directories are excluded."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "setup.py").write_text("# setup")
        egg_info = project_dir / "mypackage.egg-info"
        egg_info.mkdir()
        (egg_info / "PKG-INFO").write_text("Name: mypackage")

        collector = FileCollector(tmp_path)
        result = collector.collect(["project/"])

        # Only setup.py should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "setup.py"

    def test_collect_directory_excludes_git_directory(self, tmp_path):
        """Test that .git directories are excluded."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("# code")
        git_dir = project_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")

        collector = FileCollector(tmp_path)
        result = collector.collect(["project/"])

        # Only main.py should be collected (.git is hidden anyway)
        assert len(result.files) == 1
        assert result.files[0].name == "main.py"

    def test_collect_directory_nested_hidden_component(self, tmp_path):
        """Test that files under any hidden path component are excluded."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        visible = data_dir / "visible"
        visible.mkdir()
        (visible / "file.txt").write_text("ok")
        hidden = data_dir / ".hidden"
        hidden.mkdir()
        nested = hidden / "nested"
        nested.mkdir()
        (nested / "secret.txt").write_text("secret")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # Only data/visible/file.txt should be collected
        assert len(result.files) == 1
        assert "visible" in str(result.files[0])

    def test_collect_directory_excludes_ds_store(self, tmp_path):
        """Test that .DS_Store files are excluded."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("content")
        (data_dir / ".DS_Store").write_bytes(b"\x00\x00\x00\x01")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/"])

        # Only file.txt should be collected
        assert len(result.files) == 1
        assert result.files[0].name == "file.txt"

    def test_collect_directory_deduplicates_files(self, tmp_path):
        """Test that same file from overlapping patterns is deduplicated."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        file = data_dir / "file.txt"
        file.write_text("content")

        collector = FileCollector(tmp_path)
        # Collect the same file via directory and direct path
        result = collector.collect(["data/", "data/file.txt"])

        # File should only appear once
        assert len(result.files) == 1

    def test_collect_nonexistent_directory_adds_warning(self, tmp_path):
        """Test that non-existent directory treated as missing pattern."""
        collector = FileCollector(tmp_path)
        result = collector.collect(["nonexistent/"])

        assert len(result.files) == 0
        assert len(result.warnings) == 1
        assert "nonexistent" in result.warnings[0]


class TestFileCollectorGlob:
    """Tests for FileCollector glob pattern matching."""

    def test_collect_glob_star_matches_files_in_base_dir(self, tmp_path):
        """Test that *.json matches .json files in base directory."""
        # Setup: create json files
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("not json")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.json"])

        # Should match both json files
        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"a.json", "b.json"}
        assert result.warnings == []

    def test_collect_glob_recursive_matches_nested_files(self, tmp_path):
        """Test that **/*.csv matches .csv files in any subdirectory."""
        # Setup: create nested csv files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "x.csv").write_text("col1,col2")

        nested_dir = tmp_path / "nested" / "deep"
        nested_dir.mkdir(parents=True)
        (nested_dir / "y.csv").write_text("col1,col2")

        # Also create csv at root (should not match **/*.csv per gitwildmatch)
        (tmp_path / "root.csv").write_text("col1,col2")

        collector = FileCollector(tmp_path)
        result = collector.collect(["**/*.csv"])

        # Should match nested csv files (gitwildmatch **/ matches any directory)
        file_names = {f.name for f in result.files}
        assert "x.csv" in file_names
        assert "y.csv" in file_names

    def test_collect_glob_subdir_pattern(self, tmp_path):
        """Test that data/*.txt matches .txt files directly in data/."""
        # Setup: create txt files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "a.txt").write_text("a")
        (data_dir / "b.txt").write_text("b")

        # Nested file should NOT match data/*.txt
        nested = data_dir / "sub"
        nested.mkdir()
        (nested / "c.txt").write_text("c")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/*.txt"])

        # Should only match direct children
        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"a.txt", "b.txt"}

    def test_collect_glob_question_mark_wildcard(self, tmp_path):
        """Test that ?? matches exactly two characters."""
        # Setup: create files with varying name lengths
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "ab.txt").write_text("ab")  # matches
        (data_dir / "cd.txt").write_text("cd")  # matches
        (data_dir / "a.txt").write_text("a")  # doesn't match (1 char)
        (data_dir / "abc.txt").write_text("abc")  # doesn't match (3 chars)

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/??.txt"])

        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"ab.txt", "cd.txt"}

    def test_collect_glob_zero_matches_produces_warning(self, tmp_path):
        """Test that glob matching no files adds warning."""
        # Setup: create files that don't match pattern
        (tmp_path / "file.txt").write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.missing"])

        # Should have warning, no files
        assert len(result.files) == 0
        assert len(result.warnings) == 1
        assert "*.missing" in result.warnings[0]
        assert "matched no files" in result.warnings[0].lower()

    def test_collect_glob_excludes_hidden_files(self, tmp_path):
        """Test that glob results exclude hidden files."""
        # Setup: create visible and hidden files
        (tmp_path / "visible.txt").write_text("visible")
        (tmp_path / ".hidden.txt").write_text("hidden")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.txt"])

        # Should only match visible file
        assert len(result.files) == 1
        assert result.files[0].name == "visible.txt"

    def test_collect_glob_excludes_files_in_hidden_dirs(self, tmp_path):
        """Test that glob results exclude files in hidden directories."""
        # Setup: create files in visible and hidden directories
        visible = tmp_path / "visible"
        visible.mkdir()
        (visible / "file.txt").write_text("visible")

        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "file.txt").write_text("hidden")

        collector = FileCollector(tmp_path)
        result = collector.collect(["**/*.txt"])

        # Should only match file in visible directory
        assert len(result.files) == 1
        assert "visible" in str(result.files[0])

    def test_collect_glob_excludes_pycache(self, tmp_path):
        """Test that glob results exclude __pycache__ directories."""
        # Setup: create files including in __pycache__
        (tmp_path / "module.py").write_text("# module")
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.cpython-312.pyc").write_text("bytecode")

        collector = FileCollector(tmp_path)
        result = collector.collect(["**/*"])

        # Should not include pycache contents
        file_paths = [str(f) for f in result.files]
        assert not any("__pycache__" in p for p in file_paths)
        assert any("module.py" in p for p in file_paths)

    def test_collect_glob_excludes_node_modules(self, tmp_path):
        """Test that glob results exclude node_modules directory."""
        # Setup: create files including in node_modules
        (tmp_path / "index.js").write_text("// index")
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "dep.js").write_text("// dep")

        collector = FileCollector(tmp_path)
        result = collector.collect(["**/*.js"])

        # Should not include node_modules contents
        assert len(result.files) == 1
        assert result.files[0].name == "index.js"

    def test_collect_glob_excludes_venv(self, tmp_path):
        """Test that glob results exclude .venv and venv directories."""
        # Setup: create files including in virtual environments
        (tmp_path / "app.py").write_text("# app")

        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr/bin")

        venv2 = tmp_path / "venv"
        venv2.mkdir()
        (venv2 / "pyvenv.cfg").write_text("home = /usr/bin")

        collector = FileCollector(tmp_path)
        result = collector.collect(["**/*"])

        # Should not include venv contents
        file_paths = [str(f) for f in result.files]
        assert not any(".venv" in p for p in file_paths)
        assert not any("/venv/" in p or p.endswith("/venv") for p in file_paths)
        assert any("app.py" in p for p in file_paths)

    def test_collect_glob_excludes_git_directory(self, tmp_path):
        """Test that glob results exclude .git directory."""
        # Setup: create files including in .git
        (tmp_path / "file.txt").write_text("content")

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")

        collector = FileCollector(tmp_path)
        result = collector.collect(["**/*"])

        # Should not include .git contents (also hidden, but specifically excluded)
        file_paths = [str(f) for f in result.files]
        assert not any(".git" in p for p in file_paths)

    def test_collect_multiple_glob_patterns(self, tmp_path):
        """Test collecting with multiple glob patterns."""
        # Setup: create various files
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.yaml").write_text("key: value")
        (tmp_path / "c.txt").write_text("text")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.json", "*.yaml"])

        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"a.json", "b.yaml"}

    def test_collect_glob_with_bracket_character_class(self, tmp_path):
        """Test that [abc] character class works in glob patterns."""
        # Setup: create files
        (tmp_path / "file_a.txt").write_text("a")
        (tmp_path / "file_b.txt").write_text("b")
        (tmp_path / "file_c.txt").write_text("c")
        (tmp_path / "file_d.txt").write_text("d")

        collector = FileCollector(tmp_path)
        result = collector.collect(["file_[ab].txt"])

        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"file_a.txt", "file_b.txt"}

    def test_collect_glob_not_negation_pattern(self, tmp_path):
        """Test that patterns starting with ! are not treated as globs."""
        # A pattern like !*.txt is negation, not glob
        # This test verifies glob detection skips negation patterns
        (tmp_path / "file.txt").write_text("content")

        collector = FileCollector(tmp_path)
        # Negation pattern alone has nothing to negate (no prior inclusions)
        result = collector.collect(["!file.txt"])

        # Should have no files (nothing was included)
        # No warning because negation patterns don't warn about excluding nothing
        assert len(result.files) == 0
        assert len(result.warnings) == 0

    def test_collect_glob_tracks_pattern(self, tmp_path):
        """Test that glob pattern is tracked in patterns_matched."""
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.json"])

        assert "*.json" in result.patterns_matched
        assert len(result.patterns_matched["*.json"]) == 2

    def test_collect_glob_deduplicates_with_explicit_file(self, tmp_path):
        """Test that glob and explicit file don't duplicate."""
        (tmp_path / "data.json").write_text("{}")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data.json", "*.json"])

        # File should only appear once
        assert len(result.files) == 1
        assert result.files[0].name == "data.json"


class TestFileCollectorNegation:
    """Tests for FileCollector negation pattern support."""

    def test_negation_pattern_excludes_matching_files(self, tmp_path):
        """Test that !*.test.py excludes test files from collection."""
        # Setup: create regular and test files
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "utils.py").write_text("# utils")
        (tmp_path / "main_test.py").write_text("# test")
        (tmp_path / "utils_test.py").write_text("# test")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.py", "!*_test.py"])

        # Should exclude test files
        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"main.py", "utils.py"}

    def test_negation_pattern_order_matters(self, tmp_path):
        """Test that negation before inclusion has no effect."""
        # Setup: create json files
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (tmp_path / "config.json").write_text("{}")
        (fixtures_dir / "test_data.json").write_text("{}")

        collector = FileCollector(tmp_path)

        # Negation first - nothing to negate yet
        result = collector.collect(["!fixtures/*.json", "**/*.json"])

        # All json files should be included (negation had nothing to negate)
        file_names = {f.name for f in result.files}
        assert "config.json" in file_names
        assert "test_data.json" in file_names

    def test_negation_pattern_after_inclusion_excludes(self, tmp_path):
        """Test that negation after inclusion excludes matching files."""
        # Setup: create json files in different directories
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (tmp_path / "config.json").write_text("{}")
        (fixtures_dir / "test_data.json").write_text("{}")

        collector = FileCollector(tmp_path)

        # Include all json, then exclude fixtures
        result = collector.collect(["**/*.json", "!fixtures/*.json"])

        # Only non-fixture json should be included
        assert len(result.files) == 1
        assert result.files[0].name == "config.json"

    def test_negation_all_files_results_in_empty(self, tmp_path):
        """Test that negating all matched files results in empty collection."""
        # Setup: create json files
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.json", "!*.json"])

        # All files negated
        assert len(result.files) == 0

    def test_negation_directory_pattern(self, tmp_path):
        """Test that !fixtures/ excludes files in fixtures directory."""
        # Setup: create directory structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        fixtures_dir = data_dir / "fixtures"
        fixtures_dir.mkdir()
        (data_dir / "config.txt").write_text("config")
        (data_dir / "data.txt").write_text("data")
        (fixtures_dir / "fixture1.txt").write_text("fixture")
        (fixtures_dir / "fixture2.txt").write_text("fixture")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/", "!data/fixtures/"])

        # Should exclude fixtures directory contents
        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"config.txt", "data.txt"}

    def test_negation_with_deduplication(self, tmp_path):
        """Test that negation works correctly with deduplicated files."""
        # Setup: create files
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.txt").write_text("c")

        collector = FileCollector(tmp_path)
        # Multiple patterns matching same files, then negation
        result = collector.collect(["a.txt", "*.txt", "!b.txt"])

        # a.txt and c.txt should be in result (b.txt negated)
        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"a.txt", "c.txt"}

    def test_negation_pattern_tracked_in_patterns_matched(self, tmp_path):
        """Test that negation patterns are tracked in patterns_matched."""
        # Setup: create files
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "a_test.py").write_text("# test")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.py", "!*_test.py"])

        # Negation pattern should be tracked
        assert "!*_test.py" in result.patterns_matched
        # And should show which files it excluded
        excluded_names = [f.name for f in result.patterns_matched["!*_test.py"]]
        assert "a_test.py" in excluded_names

    def test_negation_multiple_patterns(self, tmp_path):
        """Test multiple negation patterns work together."""
        # Setup: create files
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "main_test.py").write_text("# test")
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "conftest.py").write_text("# pytest")

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.py", "!*_test.py", "!conftest.py"])

        # Should exclude both test and conftest files
        assert len(result.files) == 2
        file_names = {f.name for f in result.files}
        assert file_names == {"main.py", "__init__.py"}

    def test_negation_does_not_add_files(self, tmp_path):
        """Test that negation only removes, never adds files."""
        # Setup: create files
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.json").write_text("{}")

        collector = FileCollector(tmp_path)
        # Only include .txt, negation of .json should have no effect
        result = collector.collect(["*.txt", "!*.json"])

        # b.json was never in the set, so negation doesn't affect anything
        assert len(result.files) == 1
        assert result.files[0].name == "a.txt"

    def test_negation_no_warning_for_zero_matches(self, tmp_path):
        """Test that negation pattern matching nothing doesn't warn."""
        # Setup: create files
        (tmp_path / "a.txt").write_text("a")

        collector = FileCollector(tmp_path)
        # Negation that matches nothing shouldn't produce warning
        result = collector.collect(["*.txt", "!*.nonexistent"])

        assert len(result.files) == 1
        # No warning for negation pattern that excluded nothing
        assert len(result.warnings) == 0

    def test_overlapping_patterns_deduplicate(self, tmp_path):
        """Test that overlapping inclusion patterns deduplicate silently."""
        # Setup: create files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        config = data_dir / "config.json"
        config.write_text("{}")

        collector = FileCollector(tmp_path)
        # Same file matched by multiple patterns
        result = collector.collect(["data/", "data/config.json", "**/*.json"])

        # File should only appear once
        assert len(result.files) == 1
        assert result.files[0] == config.resolve()

    def test_negation_with_nested_directory(self, tmp_path):
        """Test negation works with deeply nested directories."""
        # Setup: create nested structure
        src = tmp_path / "src"
        src.mkdir()
        tests = src / "tests"
        tests.mkdir()
        unit = tests / "unit"
        unit.mkdir()

        (src / "main.py").write_text("# main")
        (tests / "conftest.py").write_text("# conftest")
        (unit / "test_main.py").write_text("# test")

        collector = FileCollector(tmp_path)
        result = collector.collect(["src/", "!src/tests/"])

        # Should only include main.py (tests/ excluded)
        assert len(result.files) == 1
        assert result.files[0].name == "main.py"


class TestZeroMatchWarning:
    """Tests for zero-match pattern warning emission via logger."""

    def test_zero_match_warning_logged(self, tmp_path, caplog):
        """Test that zero-match pattern emits warning via logger."""
        import logging

        caplog.set_level(logging.WARNING)

        collector = FileCollector(tmp_path)
        result = collector.collect(["*.missing"])

        # Should log warning
        assert any("*.missing" in record.message for record in caplog.records)
        assert any(record.levelno == logging.WARNING for record in caplog.records)
        # Should also store in result.warnings
        assert "*.missing" in result.warnings[0]

    def test_zero_match_warning_includes_pattern_text(self, tmp_path, caplog):
        """Test that warning includes the pattern for debugging."""
        import logging

        caplog.set_level(logging.WARNING)

        collector = FileCollector(tmp_path)
        collector.collect(["specific_missing_file.xyz"])

        # Warning should include the pattern text
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("specific_missing_file.xyz" in msg for msg in warning_messages)

    def test_zero_match_warning_collection_continues(self, tmp_path, caplog):
        """Test that collection continues after zero-match warning."""
        import logging

        caplog.set_level(logging.WARNING)

        # Create one file that exists
        (tmp_path / "exists.txt").write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["missing.txt", "exists.txt"])

        # Should have warning for missing but still collect existing
        assert len(result.files) == 1
        assert result.files[0].name == "exists.txt"
        assert len(result.warnings) == 1

    def test_negation_pattern_no_zero_match_warning(self, tmp_path, caplog):
        """Test that negation patterns don't trigger zero-match warning."""
        import logging

        caplog.set_level(logging.WARNING)

        (tmp_path / "file.txt").write_text("content")

        collector = FileCollector(tmp_path)
        # Negation that doesn't match anything
        result = collector.collect(["*.txt", "!*.nonexistent"])

        # No warning for negation pattern
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert not any("nonexistent" in msg for msg in warning_messages)
        assert len(result.warnings) == 0


class TestLargeFileWarning:
    """Tests for large file (>10MB) warning emission."""

    def test_large_file_warning_emitted(self, tmp_path, caplog):
        """Test that files >10MB emit warning via logger."""
        import logging

        from prefect._experimental.bundles._file_collector import LARGE_FILE_THRESHOLD

        caplog.set_level(logging.WARNING)

        # Create a file slightly over threshold
        large_file = tmp_path / "huge.bin"
        large_file.write_bytes(b"x" * (LARGE_FILE_THRESHOLD + 1))

        collector = FileCollector(tmp_path)
        result = collector.collect(["huge.bin"])

        # Should emit warning
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("huge.bin" in msg for msg in warning_messages)
        # File should still be collected
        assert len(result.files) == 1

    def test_large_file_warning_includes_size(self, tmp_path, caplog):
        """Test that large file warning includes file size."""
        import logging

        from prefect._experimental.bundles._file_collector import LARGE_FILE_THRESHOLD

        caplog.set_level(logging.WARNING)

        large_file = tmp_path / "big.bin"
        size = LARGE_FILE_THRESHOLD + 1024 * 1024  # threshold + 1MB
        large_file.write_bytes(b"x" * size)

        collector = FileCollector(tmp_path)
        collector.collect(["big.bin"])

        # Warning should include size info
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert len(warning_messages) >= 1
        # Check warning mentions size (in MB or bytes)
        assert any("MB" in msg or str(size) in msg for msg in warning_messages)

    def test_large_file_still_collected(self, tmp_path):
        """Test that large files are collected despite warning."""
        from prefect._experimental.bundles._file_collector import LARGE_FILE_THRESHOLD

        large_file = tmp_path / "collected.bin"
        large_file.write_bytes(b"x" * (LARGE_FILE_THRESHOLD + 100))

        collector = FileCollector(tmp_path)
        result = collector.collect(["collected.bin"])

        # File must be collected
        assert len(result.files) == 1
        assert result.files[0].name == "collected.bin"
        assert result.total_size > LARGE_FILE_THRESHOLD

    def test_large_file_threshold_constant(self):
        """Test LARGE_FILE_THRESHOLD is exported and equals 10MB."""
        from prefect._experimental.bundles._file_collector import LARGE_FILE_THRESHOLD

        assert LARGE_FILE_THRESHOLD == 10 * 1024 * 1024  # 10 MB


class TestCollectionSummary:
    """Tests for format_collection_summary function."""

    def test_format_summary_file_count_and_size(self, tmp_path):
        """Test that summary shows file count and total size."""
        from prefect._experimental.bundles._file_collector import (
            format_collection_summary,
        )

        # Create files with known sizes
        (tmp_path / "a.txt").write_text("hello")  # 5 bytes
        (tmp_path / "b.txt").write_text("world!")  # 6 bytes

        collector = FileCollector(tmp_path)
        result = collector.collect(["a.txt", "b.txt"])

        summary = format_collection_summary(result)

        # Should include count
        assert "2 files" in summary
        # Should include size (11 bytes = ~0.0 KB)
        assert "KB" in summary or "MB" in summary

    def test_format_summary_kb_format(self, tmp_path):
        """Test that small sizes show KB format."""
        from prefect._experimental.bundles._file_collector import (
            format_collection_summary,
        )

        # Create file with ~500 bytes
        (tmp_path / "small.txt").write_text("x" * 500)

        collector = FileCollector(tmp_path)
        result = collector.collect(["small.txt"])

        summary = format_collection_summary(result)

        # Should show KB for small files
        assert "KB" in summary
        assert "1 file" in summary

    def test_format_summary_mb_format(self, tmp_path):
        """Test that large sizes show MB format."""
        from prefect._experimental.bundles._file_collector import (
            format_collection_summary,
        )

        # Create file with ~2MB
        (tmp_path / "large.txt").write_bytes(b"x" * (2 * 1024 * 1024))

        collector = FileCollector(tmp_path)
        result = collector.collect(["large.txt"])

        summary = format_collection_summary(result)

        # Should show MB for large files
        assert "MB" in summary
        assert "2.0 MB" in summary or "2 MB" in summary

    def test_format_summary_human_readable(self, tmp_path):
        """Test that summary is human-readable format."""
        from prefect._experimental.bundles._file_collector import (
            format_collection_summary,
        )

        (tmp_path / "file.txt").write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["file.txt"])

        summary = format_collection_summary(result)

        # Format should be "Collected N files (X.Y KB/MB)"
        assert summary.startswith("Collected")
        assert "(" in summary and ")" in summary


class TestPreviewCollection:
    """Tests for preview_collection function."""

    def test_preview_returns_files_list(self, tmp_path):
        """Test preview_collection returns list of files."""
        from prefect._experimental.bundles._file_collector import preview_collection

        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")

        result = preview_collection(tmp_path, ["*.json"])

        assert "files" in result
        assert "a.json" in result["files"]
        assert "b.json" in result["files"]

    def test_preview_returns_file_count(self, tmp_path):
        """Test preview_collection returns file count."""
        from prefect._experimental.bundles._file_collector import preview_collection

        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.txt").write_text("c")

        result = preview_collection(tmp_path, ["*.txt"])

        assert result["file_count"] == 3

    def test_preview_returns_total_size(self, tmp_path):
        """Test preview_collection returns total size."""
        from prefect._experimental.bundles._file_collector import preview_collection

        (tmp_path / "data.txt").write_text("hello")  # 5 bytes

        result = preview_collection(tmp_path, ["*.txt"])

        assert "total_size" in result
        assert result["total_size"] == 5

    def test_preview_returns_human_readable_size(self, tmp_path):
        """Test preview_collection returns human-readable size."""
        from prefect._experimental.bundles._file_collector import preview_collection

        (tmp_path / "file.txt").write_text("content")

        result = preview_collection(tmp_path, ["*.txt"])

        assert "total_size_human" in result
        assert "KB" in result["total_size_human"] or "MB" in result["total_size_human"]

    def test_preview_returns_warnings(self, tmp_path):
        """Test preview_collection returns warnings."""
        from prefect._experimental.bundles._file_collector import preview_collection

        result = preview_collection(tmp_path, ["*.missing"])

        assert "warnings" in result
        assert len(result["warnings"]) == 1
        assert "*.missing" in result["warnings"][0]

    def test_preview_returns_patterns_matched(self, tmp_path):
        """Test preview_collection returns pattern match counts."""
        from prefect._experimental.bundles._file_collector import preview_collection

        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")

        result = preview_collection(tmp_path, ["*.json"])

        assert "patterns_matched" in result
        assert result["patterns_matched"]["*.json"] == 2

    def test_preview_does_not_modify_state(self, tmp_path):
        """Test preview_collection doesn't modify any state."""
        from prefect._experimental.bundles._file_collector import preview_collection

        (tmp_path / "file.txt").write_text("content")

        # Call preview multiple times
        result1 = preview_collection(tmp_path, ["*.txt"])
        result2 = preview_collection(tmp_path, ["*.txt"])

        # Results should be identical
        assert result1 == result2

    def test_preview_with_path_object(self, tmp_path):
        """Test preview_collection accepts Path objects."""
        from pathlib import Path

        from prefect._experimental.bundles._file_collector import preview_collection

        (tmp_path / "file.txt").write_text("content")

        result = preview_collection(Path(tmp_path), ["*.txt"])

        assert result["file_count"] == 1

    def test_preview_exported_in_all(self):
        """Test preview_collection is in __all__."""
        from prefect._experimental.bundles import _file_collector

        assert "preview_collection" in _file_collector.__all__

    def test_format_collection_summary_exported_in_all(self):
        """Test format_collection_summary is in __all__."""
        from prefect._experimental.bundles import _file_collector

        assert "format_collection_summary" in _file_collector.__all__

    def test_preview_collection_returns_excluded_by_ignore(self, tmp_path):
        """Test preview_collection returns excluded_by_ignore list."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: create .prefectignore and files
        (tmp_path / ".prefectignore").write_text("*.log\n")
        (tmp_path / "app.py").write_text("# app")
        (tmp_path / "debug.log").write_text("log content")

        result = preview_collection(tmp_path, ["*.py", "*.log"])

        assert "excluded_by_ignore" in result
        assert "debug.log" in result["excluded_by_ignore"]
        # app.py should be included, not excluded
        assert "app.py" not in result["excluded_by_ignore"]

    def test_preview_collection_returns_sensitive_warnings(self, tmp_path):
        """Test preview_collection returns sensitive_warnings list."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: create a sensitive file
        (tmp_path / ".env").write_text("SECRET=value")
        (tmp_path / "app.py").write_text("# app")

        result = preview_collection(tmp_path, [".env", "app.py"])

        assert "sensitive_warnings" in result
        assert len(result["sensitive_warnings"]) == 1
        assert ".env" in result["sensitive_warnings"][0]

    def test_preview_collection_sensitive_files_still_collected(self, tmp_path):
        """Test that sensitive files are still included (warning only)."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: create sensitive file
        (tmp_path / ".env").write_text("SECRET=value")

        result = preview_collection(tmp_path, [".env"])

        # File should be in the files list despite warning
        assert ".env" in result["files"]
        # And warning should exist
        assert len(result["sensitive_warnings"]) == 1

    def test_preview_collection_excludes_by_prefectignore(self, tmp_path):
        """Test preview_collection applies .prefectignore filtering."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: create .prefectignore and files
        (tmp_path / ".prefectignore").write_text("*.tmp\n")
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "cache.tmp").write_text("cached data")

        result = preview_collection(tmp_path, ["*.py", "*.tmp"])

        # main.py should be in files
        assert "main.py" in result["files"]
        # cache.tmp should NOT be in files (excluded by .prefectignore)
        assert "cache.tmp" not in result["files"]
        # cache.tmp should be in excluded_by_ignore
        assert "cache.tmp" in result["excluded_by_ignore"]

    def test_preview_collection_file_count_excludes_ignored(self, tmp_path):
        """Test preview_collection file_count reflects filtering."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: create files where some will be ignored
        (tmp_path / ".prefectignore").write_text("*.log\n")
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "b.py").write_text("# b")
        (tmp_path / "debug.log").write_text("log")

        result = preview_collection(tmp_path, ["*.py", "*.log"])

        # Only 2 py files should be counted (log excluded)
        assert result["file_count"] == 2

    def test_preview_collection_total_size_excludes_ignored(self, tmp_path):
        """Test preview_collection total_size reflects filtering."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: create files with known sizes
        (tmp_path / ".prefectignore").write_text("*.log\n")
        (tmp_path / "small.py").write_text("small")  # 5 bytes
        (tmp_path / "huge.log").write_text("x" * 10000)  # 10000 bytes

        result = preview_collection(tmp_path, ["*.py", "*.log"])

        # Total size should only include small.py
        assert result["total_size"] == 5

    def test_preview_collection_warnings_includes_explicit_excludes(self, tmp_path):
        """Test preview_collection warnings includes explicit exclude warnings."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: user explicitly includes a file that's ignored
        (tmp_path / ".prefectignore").write_text("important.log\n")
        (tmp_path / "important.log").write_text("important data")

        result = preview_collection(tmp_path, ["important.log"])

        # Should have warning about explicit include being ignored
        assert any("important.log" in w for w in result["warnings"])

    def test_preview_collection_multiple_sensitive_files(self, tmp_path):
        """Test preview_collection handles multiple sensitive files."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: create multiple sensitive files
        (tmp_path / ".env").write_text("SECRET=1")
        (tmp_path / "credentials.json").write_text("{}")
        (tmp_path / "server.key").write_text("key")
        (tmp_path / "app.py").write_text("# app")

        result = preview_collection(
            tmp_path, [".env", "credentials.json", "server.key", "app.py"]
        )

        # Should have 3 sensitive warnings
        assert len(result["sensitive_warnings"]) == 3
        # All 4 files should be collected (warning only)
        assert result["file_count"] == 4

    def test_preview_collection_excluded_by_ignore_empty_when_no_ignores(
        self, tmp_path
    ):
        """Test excluded_by_ignore is empty when no .prefectignore."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: no .prefectignore
        (tmp_path / "file.txt").write_text("content")

        result = preview_collection(tmp_path, ["*.txt"])

        assert result["excluded_by_ignore"] == []

    def test_preview_collection_sensitive_warnings_empty_for_safe_files(self, tmp_path):
        """Test sensitive_warnings is empty for non-sensitive files."""
        from prefect._experimental.bundles._file_collector import preview_collection

        # Setup: only safe files
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "config.yaml").write_text("key: value")

        result = preview_collection(tmp_path, ["*.py", "*.yaml"])

        assert result["sensitive_warnings"] == []
