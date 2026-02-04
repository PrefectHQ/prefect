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

from prefect._experimental.bundles.file_collector import (
    CollectionResult,
    FileCollector,
)
from prefect._experimental.bundles.path_resolver import PathValidationError


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
        # A pattern like !*.txt is negation (handled in 02-04), not glob
        # This test verifies glob detection skips negation patterns
        (tmp_path / "file.txt").write_text("content")

        collector = FileCollector(tmp_path)
        # This should NOT be treated as a glob - it's a negation pattern
        # For now it will fail (file not found) since negation isn't implemented
        result = collector.collect(["!file.txt"])

        # Should produce warning about pattern matching no files
        # (since !file.txt as a literal file doesn't exist)
        assert len(result.files) == 0
        assert len(result.warnings) == 1

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
