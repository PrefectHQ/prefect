"""Tests for naming utilities."""

from prefect._sdk.naming import (
    PYTHON_KEYWORDS,
    RESERVED_DEPLOYMENT_IDENTIFIERS,
    RESERVED_FLOW_IDENTIFIERS,
    get_reserved_names,
    make_unique_class_name,
    make_unique_identifier,
    safe_class_name,
    safe_identifier,
    to_class_name,
    to_identifier,
)


class TestToIdentifier:
    """Test conversion of names to valid Python identifiers."""

    def test_simple_name(self):
        assert to_identifier("my_flow") == "my_flow"

    def test_hyphenated_name(self):
        assert to_identifier("my-flow") == "my_flow"

    def test_spaces(self):
        assert to_identifier("my flow") == "my_flow"

    def test_mixed_separators(self):
        assert to_identifier("my-flow_name here") == "my_flow_name_here"

    def test_leading_digit(self):
        assert to_identifier("123-start") == "_123_start"

    def test_all_digits(self):
        assert to_identifier("123") == "_123"

    def test_python_keyword_class(self):
        assert to_identifier("class") == "class_"

    def test_python_keyword_import(self):
        assert to_identifier("import") == "import_"

    def test_python_keyword_def(self):
        assert to_identifier("def") == "def_"

    def test_python_keyword_return(self):
        assert to_identifier("return") == "return_"

    def test_python_keyword_if(self):
        assert to_identifier("if") == "if_"

    def test_python_keyword_for(self):
        assert to_identifier("for") == "for_"

    def test_python_keyword_while(self):
        assert to_identifier("while") == "while_"

    def test_python_keyword_try(self):
        assert to_identifier("try") == "try_"

    def test_python_keyword_except(self):
        assert to_identifier("except") == "except_"

    def test_python_keyword_with(self):
        assert to_identifier("with") == "with_"

    def test_python_keyword_as(self):
        assert to_identifier("as") == "as_"

    def test_python_keyword_from(self):
        assert to_identifier("from") == "from_"

    def test_python_keyword_lambda(self):
        assert to_identifier("lambda") == "lambda_"

    def test_python_keyword_async(self):
        assert to_identifier("async") == "async_"

    def test_python_keyword_await(self):
        assert to_identifier("await") == "await_"

    def test_unicode_normalized(self):
        """Unicode characters that can be normalized to ASCII are converted."""
        assert to_identifier("café-data") == "cafe_data"

    def test_unicode_emoji_stripped(self):
        """Emoji and non-normalizable unicode are stripped."""
        # Emoji is a symbol (category So), treated as separator, then stripped
        assert to_identifier("🚀-deploy") == "deploy"

    def test_unicode_only_emoji(self):
        """All emoji becomes _unnamed."""
        assert to_identifier("🚀🎉✨") == "_unnamed"

    def test_empty_string(self):
        assert to_identifier("") == "_unnamed"

    def test_only_special_chars(self):
        assert to_identifier("---") == "_unnamed"

    def test_consecutive_underscores_collapsed(self):
        assert to_identifier("my--flow") == "my_flow"
        assert to_identifier("my___flow") == "my_flow"
        assert to_identifier("my - flow") == "my_flow"

    def test_leading_underscore_stripped_then_reapplied_if_digit(self):
        assert to_identifier("_123flow") == "_123flow"

    def test_punctuation_becomes_underscore(self):
        assert to_identifier("my.flow") == "my_flow"
        assert to_identifier("my/flow") == "my_flow"
        assert to_identifier("my@flow") == "my_flow"

    def test_mixed_case_preserved(self):
        assert to_identifier("MyFlow") == "MyFlow"
        assert to_identifier("myFlow") == "myFlow"

    def test_accented_characters(self):
        assert to_identifier("naïve") == "naive"
        assert to_identifier("résumé") == "resume"

    def test_german_umlaut(self):
        assert to_identifier("über") == "uber"

    def test_spanish_tilde(self):
        assert to_identifier("señor") == "senor"

    def test_all_keywords_handled(self):
        """Verify all Python keywords get underscore suffix."""
        for kw in PYTHON_KEYWORDS:
            result = to_identifier(kw)
            assert result == f"{kw}_", f"Keyword {kw} not handled correctly"

    # Non-ASCII separator tests
    def test_em_dash_as_separator(self):
        """Em-dash (U+2014) should be treated as word separator."""
        assert to_identifier("my—flow") == "my_flow"

    def test_en_dash_as_separator(self):
        """En-dash (U+2013) should be treated as word separator."""
        assert to_identifier("my–flow") == "my_flow"

    def test_non_breaking_space_as_separator(self):
        """Non-breaking space (U+00A0) should be treated as word separator."""
        assert to_identifier("my\u00a0flow") == "my_flow"

    def test_figure_dash_as_separator(self):
        """Figure dash (U+2012) should be treated as word separator."""
        assert to_identifier("my\u2012flow") == "my_flow"

    def test_bracket_as_separator(self):
        """Brackets should be treated as separators."""
        assert to_identifier("a[b]c") == "a_b_c"
        assert to_identifier("a]b") == "a_b"

    def test_german_eszett(self):
        """German ß - NFKD doesn't decompose it, so it's dropped."""
        # ß does not decompose to ss via NFKD, it stays as ß and gets dropped
        assert to_identifier("straße") == "strae"

    def test_unicode_digits_dropped(self):
        """Non-ASCII digits are dropped."""
        # Arabic-Indic digits (٠١٢٣)
        assert to_identifier("test٠١٢٣") == "test"
        # Only non-ASCII digits
        assert to_identifier("٠١٢٣") == "_unnamed"


class TestToClassName:
    """Test conversion of names to valid PascalCase class names."""

    def test_simple_name(self):
        assert to_class_name("my_flow") == "MyFlow"

    def test_hyphenated_name(self):
        assert to_class_name("my-flow") == "MyFlow"

    def test_already_pascal_case(self):
        assert to_class_name("MyFlow") == "MyFlow"

    def test_spaces(self):
        assert to_class_name("my flow") == "MyFlow"

    def test_leading_digit(self):
        assert to_class_name("123-start") == "_123Start"

    def test_all_digits(self):
        assert to_class_name("123") == "_123"

    def test_python_keyword_becomes_pascal(self):
        """Keywords become valid PascalCase without underscore suffix."""
        # Python is case-sensitive, so "Class" is valid (not a keyword)
        assert to_class_name("class") == "Class"
        assert to_class_name("for") == "For"
        assert to_class_name("if") == "If"

    def test_capitalized_keyword_is_valid(self):
        """Already capitalized 'Class' should remain 'Class' (not 'Class_')."""
        assert to_class_name("Class") == "Class"

    def test_unicode_normalized(self):
        assert to_class_name("café-data") == "CafeData"

    def test_unicode_emoji_stripped(self):
        assert to_class_name("🚀-deploy") == "Deploy"

    def test_unicode_only_emoji(self):
        assert to_class_name("🚀🎉✨") == "_Unnamed"

    def test_empty_string(self):
        assert to_class_name("") == "_Unnamed"

    def test_only_special_chars(self):
        assert to_class_name("---") == "_Unnamed"

    def test_multiple_words(self):
        assert to_class_name("my-etl-flow") == "MyEtlFlow"

    def test_mixed_separators(self):
        assert to_class_name("my-flow_name here") == "MyFlowNameHere"

    def test_single_char_parts(self):
        assert to_class_name("a-b-c") == "ABC"

    def test_lowercase_preserved_after_first(self):
        """Only first char of each part is uppercased."""
        assert to_class_name("myFLOW") == "MyFLOW"
        assert to_class_name("my-FLOW") == "MyFLOW"

    def test_accented_characters(self):
        assert to_class_name("café") == "Cafe"

    def test_punctuation_as_separator(self):
        assert to_class_name("my.flow") == "MyFlow"
        assert to_class_name("my/flow") == "MyFlow"

    # Non-ASCII separator tests
    def test_em_dash_as_separator(self):
        """Em-dash should split words for PascalCase."""
        assert to_class_name("my—flow") == "MyFlow"

    def test_non_breaking_space_as_separator(self):
        """Non-breaking space should split words for PascalCase."""
        assert to_class_name("my\u00a0flow") == "MyFlow"

    def test_bracket_as_separator(self):
        """Brackets should split words for PascalCase."""
        assert to_class_name("a[b]c") == "ABC"
        assert to_class_name("a]b") == "AB"


class TestMakeUniqueIdentifier:
    """Test unique identifier generation with collision handling."""

    def test_no_collision(self):
        result = make_unique_identifier("my_flow", set())
        assert result == "my_flow"

    def test_single_collision(self):
        result = make_unique_identifier("my_flow", {"my_flow"})
        assert result == "my_flow_2"

    def test_multiple_collisions(self):
        result = make_unique_identifier("my_flow", {"my_flow", "my_flow_2"})
        assert result == "my_flow_3"

    def test_many_collisions(self):
        existing = {"my_flow", "my_flow_2", "my_flow_3", "my_flow_4"}
        result = make_unique_identifier("my_flow", existing)
        assert result == "my_flow_5"

    def test_reserved_name_avoided(self):
        # 'self' is reserved for deployment context
        result = make_unique_identifier("self", set(), RESERVED_DEPLOYMENT_IDENTIFIERS)
        assert result == "self_2"

    def test_reserved_name_with_existing(self):
        existing = {"self_2"}
        result = make_unique_identifier(
            "self", existing, RESERVED_DEPLOYMENT_IDENTIFIERS
        )
        assert result == "self_3"

    def test_run_not_reserved_in_deployment_context(self):
        # 'run' is a method name but doesn't conflict with parameter names
        result = make_unique_identifier("run", set(), RESERVED_DEPLOYMENT_IDENTIFIERS)
        assert result == "run"

    def test_flows_reserved(self):
        result = make_unique_identifier("flows", set(), RESERVED_FLOW_IDENTIFIERS)
        assert result == "flows_2"

    def test_with_options_not_reserved(self):
        """with_options is not reserved - no functional collision with method."""
        result = make_unique_identifier(
            "with_options", set(), RESERVED_DEPLOYMENT_IDENTIFIERS
        )
        assert result == "with_options"

    def test_with_infra_not_reserved(self):
        """with_infra is not reserved - no functional collision with method."""
        result = make_unique_identifier(
            "with_infra", set(), RESERVED_DEPLOYMENT_IDENTIFIERS
        )
        assert result == "with_infra"

    def test_all_reserved_in_module_context(self):
        """Test that 'all' is reserved (normalized form of '__all__')."""
        from prefect._sdk.naming import RESERVED_MODULE_IDENTIFIERS

        result = make_unique_identifier("all", set(), RESERVED_MODULE_IDENTIFIERS)
        assert result == "all_2"


class TestMakeUniqueClassName:
    """Test unique class name generation with collision handling."""

    def test_no_collision(self):
        result = make_unique_class_name("MyFlow", set())
        assert result == "MyFlow"

    def test_single_collision(self):
        result = make_unique_class_name("MyFlow", {"MyFlow"})
        assert result == "MyFlow2"

    def test_multiple_collisions(self):
        result = make_unique_class_name("MyFlow", {"MyFlow", "MyFlow2"})
        assert result == "MyFlow3"

    def test_many_collisions(self):
        existing = {"MyFlow", "MyFlow2", "MyFlow3", "MyFlow4"}
        result = make_unique_class_name("MyFlow", existing)
        assert result == "MyFlow5"


class TestGetReservedNames:
    """Test reserved name lookup by context."""

    def test_flow_context(self):
        reserved = get_reserved_names("flow")
        assert "flows" in reserved
        assert "deployments" in reserved
        assert "DeploymentName" in reserved

    def test_deployment_context(self):
        reserved = get_reserved_names("deployment")
        # Only 'self' is reserved - would break method signatures
        assert "self" in reserved
        # Method names are NOT reserved - no functional collision with parameters
        assert "run" not in reserved
        assert "run_async" not in reserved
        assert "with_options" not in reserved
        assert "with_infra" not in reserved

    def test_work_pool_context(self):
        reserved = get_reserved_names("work_pool")
        assert len(reserved) == 0

    def test_module_context(self):
        reserved = get_reserved_names("module")
        # Reserved names are in normalized form
        assert "all" in reserved

    def test_general_context(self):
        reserved = get_reserved_names("general")
        assert len(reserved) == 0


class TestSafeIdentifier:
    """Test the main safe_identifier entry point."""

    def test_simple_conversion_and_uniqueness(self):
        existing: set[str] = set()
        result1 = safe_identifier("my-flow", existing)
        existing.add(result1)
        result2 = safe_identifier("my_flow", existing)

        assert result1 == "my_flow"
        assert result2 == "my_flow_2"

    def test_with_reserved_names(self):
        # 'self' is reserved in deployment context
        result = safe_identifier("self", set(), "deployment")
        assert result == "self_2"

    def test_keyword_handling(self):
        result = safe_identifier("class", set())
        assert result == "class_"

    def test_unicode_handling(self):
        result = safe_identifier("🚀-café-deploy", set())
        # Emoji (symbol) becomes separator, stripped; café -> cafe
        assert result == "cafe_deploy"

    def test_dunder_all_reserved_in_module_context(self):
        """Test that __all__ is avoided in module context (normalizes to 'all')."""
        result = safe_identifier("__all__", set(), "module")
        # __all__ normalizes to "all" which is reserved, so becomes "all_2"
        assert result == "all_2"


class TestSafeClassName:
    """Test the main safe_class_name entry point."""

    def test_simple_conversion_and_uniqueness(self):
        existing: set[str] = set()
        result1 = safe_class_name("my-flow", existing)
        existing.add(result1)
        result2 = safe_class_name("my_flow", existing)

        assert result1 == "MyFlow"
        assert result2 == "MyFlow2"

    def test_keyword_handling(self):
        # "class" becomes "Class" which is valid (not a keyword)
        result = safe_class_name("class", set())
        assert result == "Class"

    def test_unicode_handling(self):
        result = safe_class_name("🚀-café-deploy", set())
        assert result == "CafeDeploy"


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_very_long_name(self):
        """Long names should be handled without truncation."""
        long_name = "a" * 1000
        result = to_identifier(long_name)
        assert len(result) == 1000
        assert result == long_name

    def test_mixed_unicode_and_ascii(self):
        result = to_identifier("test-日本語-flow")
        # Japanese characters are dropped, dashes are separators
        assert result == "test_flow"

    def test_chinese_characters(self):
        """Chinese characters are dropped."""
        result = to_identifier("测试流程")
        assert result == "_unnamed"

    def test_japanese_hiragana(self):
        """Japanese hiragana are dropped."""
        result = to_identifier("てすと")
        assert result == "_unnamed"

    def test_korean_characters(self):
        """Korean characters are dropped."""
        result = to_identifier("테스트")
        assert result == "_unnamed"

    def test_arabic_characters(self):
        """Arabic characters are dropped."""
        result = to_identifier("اختبار")
        assert result == "_unnamed"

    def test_cyrillic_characters(self):
        """Cyrillic characters are dropped."""
        result = to_identifier("тест")
        assert result == "_unnamed"

    def test_numeric_suffix_doesnt_conflict_with_uniqueness(self):
        """Ensure manual numeric suffixes don't cause issues."""
        existing = {"my_flow", "my_flow2", "my_flow_2"}
        result = make_unique_identifier("my_flow", existing)
        # Should find _3 since _2 exists
        assert result == "my_flow_3"

    def test_trailing_underscores_stripped(self):
        """Trailing underscores from input are stripped."""
        result = to_identifier("flow___")
        assert result == "flow"

    def test_leading_underscores_stripped(self):
        """Leading underscores from input are stripped (unless for digit prefix)."""
        result = to_identifier("___flow")
        assert result == "flow"

    def test_single_underscore_input(self):
        """Single underscore becomes _unnamed."""
        result = to_identifier("_")
        assert result == "_unnamed"

    def test_double_underscore_preserved_in_middle(self):
        """Double underscores become single underscore."""
        result = to_identifier("my__flow")
        assert result == "my_flow"

    def test_tabs_and_newlines_as_separators(self):
        """Tabs and newlines should be treated as separators."""
        assert to_identifier("my\tflow") == "my_flow"
        assert to_identifier("my\nflow") == "my_flow"
        assert to_identifier("my\rflow") == "my_flow"
