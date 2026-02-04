"""
Tests for IgnoreFilter class with .prefectignore support.

This module tests the IgnoreFilter class's ability to filter collected files
through cascading .prefectignore patterns. Tests cover:
- Basic pattern filtering (exclude matching files, preserve non-matching)
- Cascading .prefectignore from project root and flow directory
- Missing .prefectignore handling (debug log, not warning)
- Auto-exclusion of .prefectignore file itself
- Warning when user explicitly includes an ignored file
- Project root detection via pyproject.toml
- Pattern loading with comment/blank line stripping
- Gitignore syntax support (negation, directories, globs)
"""

from __future__ import annotations

import logging

from prefect._experimental.bundles.ignore_filter import (
    FilterResult,
    IgnoreFilter,
    find_project_root,
    load_ignore_patterns,
)


class TestFilterResult:
    """Tests for FilterResult dataclass."""

    def test_create_empty_filter_result(self):
        """Test creating an empty FilterResult."""
        result = FilterResult(
            included_files=[],
            excluded_by_ignore=[],
            explicitly_excluded=[],
        )
        assert result.included_files == []
        assert result.excluded_by_ignore == []
        assert result.explicitly_excluded == []

    def test_create_filter_result_with_data(self, tmp_path):
        """Test creating FilterResult with all fields populated."""
        file1 = tmp_path / "included.txt"
        file2 = tmp_path / "excluded.txt"
        file1.touch()
        file2.touch()

        result = FilterResult(
            included_files=[file1],
            excluded_by_ignore=[file2],
            explicitly_excluded=["excluded.txt was explicitly included but ignored"],
        )

        assert len(result.included_files) == 1
        assert len(result.excluded_by_ignore) == 1
        assert len(result.explicitly_excluded) == 1


class TestFindProjectRoot:
    """Tests for find_project_root function."""

    def test_find_project_root_finds_pyproject_toml(self, tmp_path):
        """Test find_project_root finds directory containing pyproject.toml."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")

        flow_dir = project_root / "src" / "flows"
        flow_dir.mkdir(parents=True)

        # Should find project_root when starting from flow_dir
        result = find_project_root(flow_dir)
        assert result == project_root

    def test_find_project_root_returns_none_when_not_found(self, tmp_path):
        """Test find_project_root returns None when no pyproject.toml exists."""
        # Create directory without pyproject.toml
        flow_dir = tmp_path / "orphan" / "flows"
        flow_dir.mkdir(parents=True)

        result = find_project_root(flow_dir)
        assert result is None

    def test_find_project_root_returns_start_dir_if_contains_pyproject(self, tmp_path):
        """Test find_project_root returns start_dir if it contains pyproject.toml."""
        # pyproject.toml in the start directory itself
        (tmp_path / "pyproject.toml").write_text("[project]")

        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_find_project_root_traverses_parents(self, tmp_path):
        """Test find_project_root correctly traverses parent directories."""
        # Create nested structure with pyproject.toml at root
        (tmp_path / "pyproject.toml").write_text("[project]")
        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)

        result = find_project_root(deep_dir)
        assert result == tmp_path


class TestLoadIgnorePatterns:
    """Tests for load_ignore_patterns function."""

    def test_load_ignore_patterns_from_flow_dir(self, tmp_path):
        """Test loading patterns from .prefectignore in flow directory."""
        (tmp_path / ".prefectignore").write_text("*.log\n*.tmp\n")

        patterns = load_ignore_patterns(tmp_path)

        assert "*.log" in patterns
        assert "*.tmp" in patterns

    def test_load_ignore_patterns_strips_comments(self, tmp_path):
        """Test that comment lines (starting with #) are stripped."""
        (tmp_path / ".prefectignore").write_text(
            "# This is a comment\n*.log\n# Another comment\n*.tmp\n"
        )

        patterns = load_ignore_patterns(tmp_path)

        # Comments should be stripped
        assert "# This is a comment" not in patterns
        assert "# Another comment" not in patterns
        # Actual patterns should remain
        assert "*.log" in patterns
        assert "*.tmp" in patterns

    def test_load_ignore_patterns_strips_blank_lines(self, tmp_path):
        """Test that blank lines are stripped."""
        (tmp_path / ".prefectignore").write_text("*.log\n\n\n*.tmp\n\n")

        patterns = load_ignore_patterns(tmp_path)

        # Should only have actual patterns
        assert len(patterns) == 2
        assert "" not in patterns

    def test_load_ignore_patterns_cascade_project_root(self, tmp_path):
        """Test that patterns cascade from project root."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        (project_root / ".prefectignore").write_text("*.log\n")

        flow_dir = project_root / "src" / "flows"
        flow_dir.mkdir(parents=True)

        patterns = load_ignore_patterns(flow_dir)

        # Should include project root patterns
        assert "*.log" in patterns

    def test_load_ignore_patterns_cascade_union_both_files(self, tmp_path):
        """Test that patterns from both project root and flow dir are combined."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        (project_root / ".prefectignore").write_text("*.log\n")

        flow_dir = project_root / "src" / "flows"
        flow_dir.mkdir(parents=True)
        (flow_dir / ".prefectignore").write_text("*.tmp\n")

        patterns = load_ignore_patterns(flow_dir)

        # Should include both patterns (union)
        assert "*.log" in patterns
        assert "*.tmp" in patterns

    def test_load_ignore_patterns_missing_prefectignore_debug_log(
        self, tmp_path, caplog
    ):
        """Test that missing .prefectignore emits debug log, not warning."""
        caplog.set_level(logging.DEBUG)

        # No .prefectignore in tmp_path
        patterns = load_ignore_patterns(tmp_path)

        # Should return empty list
        assert patterns == []

        # Should NOT have warning logs, only debug
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0


class TestIgnoreFilter:
    """Tests for IgnoreFilter class."""

    def test_filter_excludes_matching_files(self, tmp_path):
        """Test that files matching .prefectignore patterns are excluded."""
        # Setup: create .prefectignore and files
        (tmp_path / ".prefectignore").write_text("*.log\n")
        keep_file = tmp_path / "app.py"
        keep_file.touch()
        log_file = tmp_path / "debug.log"
        log_file.touch()

        # Create filter and filter files
        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([keep_file, log_file])

        # log file should be excluded
        assert keep_file in result.included_files
        assert log_file in result.excluded_by_ignore
        assert log_file not in result.included_files

    def test_filter_preserves_non_matching_files(self, tmp_path):
        """Test that files not matching patterns are preserved."""
        # Setup: create .prefectignore that doesn't match test files
        (tmp_path / ".prefectignore").write_text("*.log\n")
        file1 = tmp_path / "main.py"
        file2 = tmp_path / "config.yaml"
        file1.touch()
        file2.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([file1, file2])

        # Both files should be included
        assert file1 in result.included_files
        assert file2 in result.included_files
        assert len(result.excluded_by_ignore) == 0

    def test_prefectignore_auto_excluded(self, tmp_path):
        """Test that .prefectignore file itself is auto-excluded."""
        # Setup
        (tmp_path / ".prefectignore").write_text("*.log\n")
        prefectignore = tmp_path / ".prefectignore"
        other_file = tmp_path / "main.py"
        other_file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([prefectignore, other_file])

        # .prefectignore should be excluded
        assert prefectignore in result.excluded_by_ignore
        assert prefectignore not in result.included_files
        # Other file should be included
        assert other_file in result.included_files

    def test_explicit_include_excluded_warns(self, tmp_path):
        """Test warning when user explicitly includes a file that's ignored."""
        # Setup: ignore *.secret and have user explicitly include one
        (tmp_path / ".prefectignore").write_text("*.secret\n")
        secret_file = tmp_path / "api.secret"
        secret_file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        # Pass explicit_patterns to indicate user's intent
        result = ignore_filter.filter([secret_file], explicit_patterns=["api.secret"])

        # File should be excluded
        assert secret_file in result.excluded_by_ignore
        # Should have explicit exclusion warning
        assert len(result.explicitly_excluded) >= 1
        # Warning should mention the file
        assert any("api.secret" in warning for warning in result.explicitly_excluded)

    def test_cascade_loads_project_root_patterns(self, tmp_path):
        """Test that IgnoreFilter loads patterns from project root."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        (project_root / ".prefectignore").write_text("*.log\n")

        flow_dir = project_root / "src" / "flows"
        flow_dir.mkdir(parents=True)

        log_file = flow_dir / "debug.log"
        log_file.touch()
        py_file = flow_dir / "flow.py"
        py_file.touch()

        ignore_filter = IgnoreFilter(flow_dir)
        result = ignore_filter.filter([log_file, py_file])

        # Log file should be excluded by project root pattern
        assert log_file in result.excluded_by_ignore
        assert py_file in result.included_files

    def test_cascade_loads_flow_dir_patterns(self, tmp_path):
        """Test that IgnoreFilter loads patterns from flow directory."""
        # Setup: .prefectignore in flow_dir only
        (tmp_path / ".prefectignore").write_text("*.tmp\n")
        tmp_file = tmp_path / "cache.tmp"
        tmp_file.touch()
        py_file = tmp_path / "main.py"
        py_file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([tmp_file, py_file])

        assert tmp_file in result.excluded_by_ignore
        assert py_file in result.included_files

    def test_cascade_union_both_files(self, tmp_path):
        """Test that patterns from both project root and flow dir apply."""
        # Create project structure with both .prefectignore files
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]")
        (project_root / ".prefectignore").write_text("*.log\n")

        flow_dir = project_root / "src" / "flows"
        flow_dir.mkdir(parents=True)
        (flow_dir / ".prefectignore").write_text("*.tmp\n")

        # Create test files
        log_file = flow_dir / "app.log"
        log_file.touch()
        tmp_file = flow_dir / "cache.tmp"
        tmp_file.touch()
        py_file = flow_dir / "flow.py"
        py_file.touch()

        ignore_filter = IgnoreFilter(flow_dir)
        result = ignore_filter.filter([log_file, tmp_file, py_file])

        # Both log and tmp should be excluded (union of patterns)
        assert log_file in result.excluded_by_ignore
        assert tmp_file in result.excluded_by_ignore
        assert py_file in result.included_files

    def test_gitignore_syntax_negation(self, tmp_path):
        """Test that gitignore negation syntax works."""
        # Exclude all logs except important.log
        (tmp_path / ".prefectignore").write_text("*.log\n!important.log\n")
        important_log = tmp_path / "important.log"
        important_log.touch()
        debug_log = tmp_path / "debug.log"
        debug_log.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([important_log, debug_log])

        # important.log should be included (negated)
        assert important_log in result.included_files
        # debug.log should still be excluded
        assert debug_log in result.excluded_by_ignore

    def test_gitignore_syntax_directories(self, tmp_path):
        """Test that directory patterns (ending with /) work."""
        # Exclude __pycache__/ directory
        (tmp_path / ".prefectignore").write_text("__pycache__/\n")

        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        pyc_file = pycache / "module.cpython-311.pyc"
        pyc_file.touch()

        main_py = tmp_path / "main.py"
        main_py.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([pyc_file, main_py])

        # File in __pycache__ should be excluded
        assert pyc_file in result.excluded_by_ignore
        assert main_py in result.included_files

    def test_gitignore_syntax_globs(self, tmp_path):
        """Test that glob patterns work (**, *, ?)."""
        # Exclude all .pyc files anywhere
        (tmp_path / ".prefectignore").write_text("**/*.pyc\n")

        deep_dir = tmp_path / "src" / "utils"
        deep_dir.mkdir(parents=True)
        pyc_file = deep_dir / "helper.pyc"
        pyc_file.touch()
        py_file = deep_dir / "helper.py"
        py_file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([pyc_file, py_file])

        assert pyc_file in result.excluded_by_ignore
        assert py_file in result.included_files

    def test_no_prefectignore_allows_all_files(self, tmp_path):
        """Test that missing .prefectignore allows all files through."""
        # No .prefectignore file
        file1 = tmp_path / "a.py"
        file2 = tmp_path / "b.log"
        file1.touch()
        file2.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([file1, file2])

        # All files should be included (except .prefectignore if present)
        assert file1 in result.included_files
        assert file2 in result.included_files
        assert len(result.excluded_by_ignore) == 0

    def test_filter_handles_files_relative_to_flow_dir(self, tmp_path):
        """Test filter handles files in subdirectories correctly."""
        (tmp_path / ".prefectignore").write_text("data/*.csv\n")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv_file = data_dir / "input.csv"
        csv_file.touch()
        json_file = data_dir / "config.json"
        json_file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([csv_file, json_file])

        # CSV should be excluded by pattern
        assert csv_file in result.excluded_by_ignore
        assert json_file in result.included_files

    def test_filter_empty_file_list(self, tmp_path):
        """Test filtering empty file list."""
        (tmp_path / ".prefectignore").write_text("*.log\n")

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([])

        assert result.included_files == []
        assert result.excluded_by_ignore == []
        assert result.explicitly_excluded == []


class TestIgnoreFilterEdgeCases:
    """Edge case tests for IgnoreFilter."""

    def test_empty_prefectignore_file(self, tmp_path):
        """Test handling of empty .prefectignore file."""
        (tmp_path / ".prefectignore").write_text("")
        file = tmp_path / "test.py"
        file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([file])

        # File should be included (no patterns to exclude)
        assert file in result.included_files

    def test_prefectignore_only_comments(self, tmp_path):
        """Test .prefectignore with only comments."""
        (tmp_path / ".prefectignore").write_text("# Comment 1\n# Comment 2\n")
        file = tmp_path / "test.py"
        file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([file])

        # File should be included (no actual patterns)
        assert file in result.included_files

    def test_prefectignore_whitespace_lines(self, tmp_path):
        """Test that whitespace-only lines are handled."""
        (tmp_path / ".prefectignore").write_text("*.log\n   \n\t\n*.tmp\n")
        log_file = tmp_path / "debug.log"
        log_file.touch()
        tmp_file = tmp_path / "cache.tmp"
        tmp_file.touch()
        py_file = tmp_path / "main.py"
        py_file.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([log_file, tmp_file, py_file])

        # Both log and tmp should be excluded
        assert log_file in result.excluded_by_ignore
        assert tmp_file in result.excluded_by_ignore
        assert py_file in result.included_files

    def test_nested_prefectignore_in_path(self, tmp_path):
        """Test .prefectignore file in nested directory is auto-excluded."""
        subdir = tmp_path / "sub"
        subdir.mkdir()
        nested_ignore = subdir / ".prefectignore"
        nested_ignore.write_text("*.tmp")

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter([nested_ignore])

        # Any .prefectignore file should be auto-excluded
        assert nested_ignore in result.excluded_by_ignore

    def test_multiple_explicit_patterns_matched(self, tmp_path):
        """Test warning for multiple explicitly included files being ignored."""
        (tmp_path / ".prefectignore").write_text("*.secret\n*.key\n")
        secret1 = tmp_path / "api.secret"
        secret2 = tmp_path / "private.key"
        secret1.touch()
        secret2.touch()

        ignore_filter = IgnoreFilter(tmp_path)
        result = ignore_filter.filter(
            [secret1, secret2],
            explicit_patterns=["api.secret", "private.key"],
        )

        # Both should be excluded
        assert secret1 in result.excluded_by_ignore
        assert secret2 in result.excluded_by_ignore
        # Should have warnings for both
        assert len(result.explicitly_excluded) >= 2


class TestSensitivePatterns:
    """Tests for sensitive file pattern detection."""

    def test_sensitive_patterns_constant_defined(self):
        """Test SENSITIVE_PATTERNS constant is defined and exported."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert isinstance(SENSITIVE_PATTERNS, list)
        assert len(SENSITIVE_PATTERNS) == 7

    def test_sensitive_patterns_contains_env_files(self):
        """Test SENSITIVE_PATTERNS contains .env* pattern."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert ".env*" in SENSITIVE_PATTERNS

    def test_sensitive_patterns_contains_pem_files(self):
        """Test SENSITIVE_PATTERNS contains *.pem pattern."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert "*.pem" in SENSITIVE_PATTERNS

    def test_sensitive_patterns_contains_key_files(self):
        """Test SENSITIVE_PATTERNS contains *.key pattern."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert "*.key" in SENSITIVE_PATTERNS

    def test_sensitive_patterns_contains_credentials_files(self):
        """Test SENSITIVE_PATTERNS contains credentials.* pattern."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert "credentials.*" in SENSITIVE_PATTERNS

    def test_sensitive_patterns_contains_rsa_keys(self):
        """Test SENSITIVE_PATTERNS contains *_rsa pattern."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert "*_rsa" in SENSITIVE_PATTERNS

    def test_sensitive_patterns_contains_p12_files(self):
        """Test SENSITIVE_PATTERNS contains *.p12 pattern."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert "*.p12" in SENSITIVE_PATTERNS

    def test_sensitive_patterns_contains_secrets_files(self):
        """Test SENSITIVE_PATTERNS contains secrets.* pattern."""
        from prefect._experimental.bundles.ignore_filter import SENSITIVE_PATTERNS

        assert "secrets.*" in SENSITIVE_PATTERNS


class TestCheckSensitiveFiles:
    """Tests for check_sensitive_files function."""

    def test_check_sensitive_detects_env_files(self, tmp_path):
        """Test check_sensitive_files detects .env files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        env_file = tmp_path / ".env"
        env_file.touch()

        warnings = check_sensitive_files([env_file], tmp_path)

        assert len(warnings) == 1
        assert ".env" in warnings[0]

    def test_check_sensitive_detects_env_local(self, tmp_path):
        """Test check_sensitive_files detects .env.local files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        env_file = tmp_path / ".env.local"
        env_file.touch()

        warnings = check_sensitive_files([env_file], tmp_path)

        assert len(warnings) == 1
        assert ".env.local" in warnings[0]

    def test_check_sensitive_detects_pem_files(self, tmp_path):
        """Test check_sensitive_files detects .pem files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        pem_file = tmp_path / "server.pem"
        pem_file.touch()

        warnings = check_sensitive_files([pem_file], tmp_path)

        assert len(warnings) == 1
        assert "server.pem" in warnings[0]

    def test_check_sensitive_detects_key_files(self, tmp_path):
        """Test check_sensitive_files detects .key files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        key_file = tmp_path / "private.key"
        key_file.touch()

        warnings = check_sensitive_files([key_file], tmp_path)

        assert len(warnings) == 1
        assert "private.key" in warnings[0]

    def test_check_sensitive_detects_credentials_files(self, tmp_path):
        """Test check_sensitive_files detects credentials.* files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        creds_file = tmp_path / "credentials.json"
        creds_file.touch()

        warnings = check_sensitive_files([creds_file], tmp_path)

        assert len(warnings) == 1
        assert "credentials.json" in warnings[0]

    def test_check_sensitive_detects_rsa_keys(self, tmp_path):
        """Test check_sensitive_files detects *_rsa files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        rsa_file = tmp_path / "id_rsa"
        rsa_file.touch()

        warnings = check_sensitive_files([rsa_file], tmp_path)

        assert len(warnings) == 1
        assert "id_rsa" in warnings[0]

    def test_check_sensitive_detects_p12_files(self, tmp_path):
        """Test check_sensitive_files detects .p12 files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        p12_file = tmp_path / "certificate.p12"
        p12_file.touch()

        warnings = check_sensitive_files([p12_file], tmp_path)

        assert len(warnings) == 1
        assert "certificate.p12" in warnings[0]

    def test_check_sensitive_detects_secrets_files(self, tmp_path):
        """Test check_sensitive_files detects secrets.* files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        secrets_file = tmp_path / "secrets.yaml"
        secrets_file.touch()

        warnings = check_sensitive_files([secrets_file], tmp_path)

        assert len(warnings) == 1
        assert "secrets.yaml" in warnings[0]

    def test_check_sensitive_warning_format(self, tmp_path):
        """Test warning format includes pattern that matched."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        env_file = tmp_path / ".env"
        env_file.touch()

        warnings = check_sensitive_files([env_file], tmp_path)

        # Warning should include: "matches sensitive pattern {pattern}"
        assert "matches sensitive pattern" in warnings[0]
        assert ".env*" in warnings[0]

    def test_check_sensitive_suggests_prefectignore(self, tmp_path):
        """Test warning suggests adding to .prefectignore."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        key_file = tmp_path / "server.key"
        key_file.touch()

        warnings = check_sensitive_files([key_file], tmp_path)

        # Warning should suggest adding to .prefectignore
        assert ".prefectignore" in warnings[0]
        assert "Consider adding" in warnings[0]

    def test_check_sensitive_returns_empty_for_safe_files(self, tmp_path):
        """Test check_sensitive_files returns empty for non-sensitive files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        safe_file = tmp_path / "main.py"
        safe_file.touch()

        warnings = check_sensitive_files([safe_file], tmp_path)

        assert warnings == []

    def test_check_sensitive_multiple_files(self, tmp_path):
        """Test check_sensitive_files handles multiple files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        env_file = tmp_path / ".env"
        key_file = tmp_path / "server.key"
        safe_file = tmp_path / "main.py"
        env_file.touch()
        key_file.touch()
        safe_file.touch()

        warnings = check_sensitive_files([env_file, key_file, safe_file], tmp_path)

        # Should have warnings for sensitive files only
        assert len(warnings) == 2

    def test_check_sensitive_nested_file(self, tmp_path):
        """Test check_sensitive_files handles nested sensitive files."""
        from prefect._experimental.bundles.ignore_filter import check_sensitive_files

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        env_file = config_dir / ".env.production"
        env_file.touch()

        warnings = check_sensitive_files([env_file], tmp_path)

        assert len(warnings) == 1
        # Should show relative path
        assert "config/.env.production" in warnings[0]


class TestEmitExcludedWarning:
    """Tests for emit_excluded_warning function."""

    def test_emit_excluded_warning_batched(self, tmp_path, caplog):
        """Test emit_excluded_warning batches files into single warning."""
        from prefect._experimental.bundles.ignore_filter import emit_excluded_warning

        caplog.set_level(logging.WARNING)

        # Create 3 excluded files
        files = []
        for i in range(3):
            f = tmp_path / f"file{i}.log"
            f.touch()
            files.append(f)

        emit_excluded_warning(files, tmp_path)

        # Should emit single warning
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 1
        # Warning should mention count
        assert "3 files excluded" in warning_records[0].message

    def test_emit_excluded_warning_includes_file_names(self, tmp_path, caplog):
        """Test emit_excluded_warning includes file names."""
        from prefect._experimental.bundles.ignore_filter import emit_excluded_warning

        caplog.set_level(logging.WARNING)

        file1 = tmp_path / "debug.log"
        file2 = tmp_path / "error.log"
        file1.touch()
        file2.touch()

        emit_excluded_warning([file1, file2], tmp_path)

        warning_msg = caplog.records[-1].message
        assert "debug.log" in warning_msg
        assert "error.log" in warning_msg

    def test_emit_excluded_warning_truncates_after_10(self, tmp_path, caplog):
        """Test emit_excluded_warning truncates list after 10 files."""
        from prefect._experimental.bundles.ignore_filter import emit_excluded_warning

        caplog.set_level(logging.WARNING)

        # Create 15 excluded files
        files = []
        for i in range(15):
            f = tmp_path / f"file{i:02d}.log"
            f.touch()
            files.append(f)

        emit_excluded_warning(files, tmp_path)

        warning_msg = caplog.records[-1].message
        # Should show first 10 files
        assert "file00.log" in warning_msg
        assert "file09.log" in warning_msg
        # Should NOT show files after 10
        assert "file10.log" not in warning_msg
        # Should indicate more files
        assert "and 5 more" in warning_msg

    def test_emit_excluded_warning_mentions_prefectignore(self, tmp_path, caplog):
        """Test emit_excluded_warning mentions .prefectignore."""
        from prefect._experimental.bundles.ignore_filter import emit_excluded_warning

        caplog.set_level(logging.WARNING)

        file = tmp_path / "excluded.log"
        file.touch()

        emit_excluded_warning([file], tmp_path)

        warning_msg = caplog.records[-1].message
        assert ".prefectignore" in warning_msg

    def test_emit_excluded_warning_empty_list_no_warning(self, tmp_path, caplog):
        """Test emit_excluded_warning emits nothing for empty list."""
        from prefect._experimental.bundles.ignore_filter import emit_excluded_warning

        caplog.set_level(logging.WARNING)

        emit_excluded_warning([], tmp_path)

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 0

    def test_emit_excluded_warning_exactly_10_no_truncation(self, tmp_path, caplog):
        """Test emit_excluded_warning shows all 10 files without truncation."""
        from prefect._experimental.bundles.ignore_filter import emit_excluded_warning

        caplog.set_level(logging.WARNING)

        # Create exactly 10 files
        files = []
        for i in range(10):
            f = tmp_path / f"file{i}.log"
            f.touch()
            files.append(f)

        emit_excluded_warning(files, tmp_path)

        warning_msg = caplog.records[-1].message
        # Should NOT show "and X more"
        assert "and" not in warning_msg or "more" not in warning_msg
        # Should show 10 files
        assert "10 files excluded" in warning_msg
