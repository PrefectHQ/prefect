"""Tests for text search query parser

Tests the parsing of text search queries according to the following syntax:

- Space-separated terms → OR logic (include)
- Prefix with `-` or `!` → Exclude term
- Prefix with `+` → Required term (AND logic, future)
- Quote phrases → Match exact phrase
- Case-insensitive, substring matching
"""

import pytest

from prefect.server.utilities.text_search_parser import (
    TextSearchQuery,
    parse_text_search_query,
)


class TestBasicParsing:
    """Test basic query parsing functionality"""

    def test_empty_string(self):
        result = parse_text_search_query("")
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_whitespace_only(self):
        result = parse_text_search_query("   \t\n  ")
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_single_term(self):
        result = parse_text_search_query("error")
        assert result == TextSearchQuery(include=["error"], exclude=[], required=[])

    def test_multiple_terms_or_logic(self):
        result = parse_text_search_query("error warning timeout")
        assert result == TextSearchQuery(
            include=["error", "warning", "timeout"], exclude=[], required=[]
        )

    def test_multiple_spaces_between_terms(self):
        result = parse_text_search_query("error    warning\t\ttimeout")
        assert result == TextSearchQuery(
            include=["error", "warning", "timeout"], exclude=[], required=[]
        )

    def test_leading_trailing_whitespace(self):
        result = parse_text_search_query("  error warning  ")
        assert result == TextSearchQuery(
            include=["error", "warning"], exclude=[], required=[]
        )

    def test_whitespace_preserved_in_quotes_only(self):
        # Multiple spaces between terms should be collapsed, but preserved in quotes
        result = parse_text_search_query('hello     "world again "')
        assert result == TextSearchQuery(
            include=["hello", "world again "], exclude=[], required=[]
        )


class TestNegativeTerms:
    """Test exclusion syntax with - and ! prefixes"""

    def test_minus_prefix_single_term(self):
        result = parse_text_search_query("-debug")
        assert result == TextSearchQuery(include=[], exclude=["debug"], required=[])

    def test_exclamation_prefix_single_term(self):
        result = parse_text_search_query("!debug")
        assert result == TextSearchQuery(include=[], exclude=["debug"], required=[])

    def test_mixed_negative_prefixes(self):
        result = parse_text_search_query("error -debug !test")
        assert result == TextSearchQuery(
            include=["error"], exclude=["debug", "test"], required=[]
        )

    def test_minus_only(self):
        result = parse_text_search_query("-")
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_exclamation_only(self):
        result = parse_text_search_query("!")
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_multiple_prefixes(self):
        # Double prefixes should be treated as part of the term
        result = parse_text_search_query("--term")
        assert result == TextSearchQuery(include=[], exclude=["-term"], required=[])

    def test_prefix_mixed_with_content(self):
        result = parse_text_search_query("!-term")
        assert result == TextSearchQuery(include=[], exclude=["-term"], required=[])

    def test_dash_in_middle_of_word(self):
        # Dashes in middle should be preserved as part of term
        result = parse_text_search_query("task-run flow-name")
        assert result == TextSearchQuery(
            include=["task-run", "flow-name"], exclude=[], required=[]
        )

    def test_dash_at_end_of_word(self):
        # Dash at end should be preserved
        result = parse_text_search_query("prefix-")
        assert result == TextSearchQuery(include=["prefix-"], exclude=[], required=[])


class TestRequiredTerms:
    """Test required/AND syntax with + prefix (future feature)"""

    def test_plus_prefix_single_term(self):
        result = parse_text_search_query("+required")
        assert result == TextSearchQuery(include=[], exclude=[], required=["required"])

    def test_plus_only(self):
        result = parse_text_search_query("+")
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_mixed_required_with_other_terms(self):
        result = parse_text_search_query("include +required -excluded")
        assert result == TextSearchQuery(
            include=["include"], exclude=["excluded"], required=["required"]
        )

    def test_multiple_required_terms(self):
        result = parse_text_search_query("+error +connection")
        assert result == TextSearchQuery(
            include=[], exclude=[], required=["error", "connection"]
        )


class TestQuotedPhrases:
    """Test quoted phrase handling"""

    def test_simple_quoted_phrase(self):
        result = parse_text_search_query('"connection timeout"')
        assert result == TextSearchQuery(
            include=["connection timeout"], exclude=[], required=[]
        )

    def test_multiple_quoted_phrases(self):
        result = parse_text_search_query('"phrase one" "phrase two"')
        assert result == TextSearchQuery(
            include=["phrase one", "phrase two"], exclude=[], required=[]
        )

    def test_quoted_phrase_with_regular_terms(self):
        result = parse_text_search_query('error "connection timeout" warning')
        assert result == TextSearchQuery(
            include=["error", "connection timeout", "warning"], exclude=[], required=[]
        )

    def test_excluded_quoted_phrase(self):
        result = parse_text_search_query('-"debug mode"')
        assert result == TextSearchQuery(
            include=[], exclude=["debug mode"], required=[]
        )

    def test_excluded_quoted_phrase_with_exclamation(self):
        result = parse_text_search_query('!"test environment"')
        assert result == TextSearchQuery(
            include=[], exclude=["test environment"], required=[]
        )

    def test_required_quoted_phrase(self):
        result = parse_text_search_query('+"connection established"')
        assert result == TextSearchQuery(
            include=[], exclude=[], required=["connection established"]
        )

    def test_empty_quoted_string(self):
        result = parse_text_search_query('""')
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_whitespace_only_quoted_string(self):
        result = parse_text_search_query('"   "')
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_unclosed_quote_at_end(self):
        # Unclosed quote should include everything to end as literal term
        result = parse_text_search_query('error "unclosed quote')
        assert result == TextSearchQuery(
            include=["error", "unclosed quote"], exclude=[], required=[]
        )

    def test_unclosed_quote_with_following_terms(self):
        # Unclosed quote should consume rest of string
        result = parse_text_search_query('error "unclosed and more terms')
        assert result == TextSearchQuery(
            include=["error", "unclosed and more terms"], exclude=[], required=[]
        )

    def test_quotes_with_special_characters(self):
        result = parse_text_search_query('"error: connection failed!"')
        assert result == TextSearchQuery(
            include=["error: connection failed!"], exclude=[], required=[]
        )

    def test_escaped_quotes_within_phrases(self):
        # Backslash escapes allow quotes within phrases
        result = parse_text_search_query(r'"phrase with \"inner\" quotes"')
        assert result == TextSearchQuery(
            include=['phrase with "inner" quotes'], exclude=[], required=[]
        )

    def test_escaped_backslashes(self):
        # Escaped backslashes should be literal
        result = parse_text_search_query(r'"path\\to\\file"')
        assert result == TextSearchQuery(
            include=[r"path\to\file"], exclude=[], required=[]
        )

    def test_escaped_quote_at_end(self):
        # Escaped quote at end of phrase
        result = parse_text_search_query(r'"error message\""')
        assert result == TextSearchQuery(
            include=['error message"'], exclude=[], required=[]
        )

    def test_escaped_quote_at_start(self):
        # Escaped quote at start of phrase
        result = parse_text_search_query(r'"\"quoted\" message"')
        assert result == TextSearchQuery(
            include=['"quoted" message'], exclude=[], required=[]
        )

    def test_multiple_escaped_quotes(self):
        # Multiple escaped quotes in one phrase
        result = parse_text_search_query(
            r'"He said \"Hello\" and she said \"Goodbye\""'
        )
        assert result == TextSearchQuery(
            include=['He said "Hello" and she said "Goodbye"'], exclude=[], required=[]
        )

    def test_backslash_without_quote_is_literal(self):
        # Backslash not followed by quote should be literal
        result = parse_text_search_query(r'"path\folder\file"')
        assert result == TextSearchQuery(
            include=[r"path\folder\file"], exclude=[], required=[]
        )

    def test_nested_quotes_without_escaping(self):
        # Without escaping, inner quotes end the phrase early
        result = parse_text_search_query('"phrase with "inner" quotes"')
        assert result == TextSearchQuery(
            include=["phrase with ", "inner", " quotes"], exclude=[], required=[]
        )


class TestComplexScenarios:
    """Test complex real-world query scenarios"""

    def test_debugging_failed_flow_run(self):
        # Scenario: User knows the flow failed with a connection error
        result = parse_text_search_query('"connection" error -debug')
        assert result == TextSearchQuery(
            include=["connection", "error"], exclude=["debug"], required=[]
        )

    def test_production_issues_only(self):
        # Scenario: User wants errors from production only
        result = parse_text_search_query("error exception -test -staging -dev")
        assert result == TextSearchQuery(
            include=["error", "exception"],
            exclude=["test", "staging", "dev"],
            required=[],
        )

    def test_specific_error_message(self):
        # Scenario: User remembers exact error message
        result = parse_text_search_query('"Unable to connect to database"')
        assert result == TextSearchQuery(
            include=["Unable to connect to database"], exclude=[], required=[]
        )

    def test_complex_mixed_syntax(self):
        # Ultimate complexity test with all syntax features
        result = parse_text_search_query(
            '"connection timeout" error -debug !test +required'
        )
        assert result == TextSearchQuery(
            include=["connection timeout", "error"],
            exclude=["debug", "test"],
            required=["required"],
        )

    def test_flow_run_id_search(self):
        # Scenario: User has a flow run ID
        result = parse_text_search_query("abc123-def456-789")
        assert result == TextSearchQuery(
            include=["abc123-def456-789"], exclude=[], required=[]
        )

    def test_environment_filtering(self):
        result = parse_text_search_query("deployment -test -staging")
        assert result == TextSearchQuery(
            include=["deployment"], exclude=["test", "staging"], required=[]
        )


class TestEdgeCasesAndLimitations:
    """Test edge cases and documented limitations"""

    def test_literal_dash_at_start_not_supported(self):
        # Searching for literal `-` at start is not supported
        # This should be treated as exclusion, not literal dash
        result = parse_text_search_query("-")
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_special_characters_preserved_in_terms(self):
        result = parse_text_search_query("error@domain.com task#123 flow$var")
        assert result == TextSearchQuery(
            include=["error@domain.com", "task#123", "flow$var"],
            exclude=[],
            required=[],
        )

    def test_unicode_characters(self):
        result = parse_text_search_query("errör ñame 中文")
        assert result == TextSearchQuery(
            include=["errör", "ñame", "中文"], exclude=[], required=[]
        )

    def test_very_long_terms(self):
        long_term = "a" * 100
        result = parse_text_search_query(f"error {long_term}")
        assert result == TextSearchQuery(
            include=["error", long_term], exclude=[], required=[]
        )

    def test_many_terms(self):
        # Test parsing many terms efficiently (keep under 200 char limit)
        terms = [f"t{i}" for i in range(30)]  # t0 t1 t2... fits in 200 chars
        query = " ".join(terms)
        result = parse_text_search_query(query)
        assert result == TextSearchQuery(include=terms, exclude=[], required=[])

    def test_alternating_prefixes(self):
        result = parse_text_search_query(
            "include -exclude +required -exclude2 include2"
        )
        assert result == TextSearchQuery(
            include=["include", "include2"],
            exclude=["exclude", "exclude2"],
            required=["required"],
        )

    def test_quoted_phrases_with_prefixes_inside(self):
        # Prefixes inside quotes should be literal
        result = parse_text_search_query('"error -debug +required"')
        assert result == TextSearchQuery(
            include=["error -debug +required"], exclude=[], required=[]
        )

    def test_mixed_quote_styles_not_supported(self):
        # Only double quotes have special meaning
        result = parse_text_search_query("'single quotes' error")
        assert result == TextSearchQuery(
            include=["'single", "quotes'", "error"], exclude=[], required=[]
        )

    def test_backslash_escape_only_for_quotes(self):
        # Backslashes only escape quotes, other backslashes are literal
        result = parse_text_search_query(r'error\test "quote\"inside"')
        assert result == TextSearchQuery(
            include=[r"error\test", 'quote"inside'], exclude=[], required=[]
        )

    def test_prefix_with_quotes_complex(self):
        result = parse_text_search_query(
            '+"required phrase" -"excluded phrase" "normal phrase"'
        )
        assert result == TextSearchQuery(
            include=["normal phrase"],
            exclude=["excluded phrase"],
            required=["required phrase"],
        )


class TestQueryValidation:
    """Test query validation (character limits enforced at API layer)"""

    def test_handles_very_long_queries(self):
        # Parser should handle long queries (limits enforced in EventFilter/LogFilter)
        long_query = "a" * 500
        result = parse_text_search_query(long_query)
        assert result == TextSearchQuery(include=[long_query], exclude=[], required=[])

    def test_handles_long_quoted_phrases(self):
        # Parser should handle long quoted content
        long_phrase = "a" * 300
        query_with_quotes = f'"{long_phrase}"'
        result = parse_text_search_query(query_with_quotes)
        assert result == TextSearchQuery(include=[long_phrase], exclude=[], required=[])


class TestParserRobustness:
    """Test parser handles malformed input gracefully"""

    def test_multiple_consecutive_quotes(self):
        result = parse_text_search_query('""error""')
        # Should treat as empty quote, then "error", then empty quote
        assert result == TextSearchQuery(include=["error"], exclude=[], required=[])

    def test_quote_at_start_and_end(self):
        result = parse_text_search_query('"start error end"')
        assert result == TextSearchQuery(
            include=["start error end"], exclude=[], required=[]
        )

    def test_only_prefixes(self):
        result = parse_text_search_query("- ! +")
        assert result == TextSearchQuery(include=[], exclude=[], required=[])

    def test_prefix_followed_by_space(self):
        result = parse_text_search_query("error - debug")
        # Dash followed by space should be ignored completely, both error and debug included
        assert result == TextSearchQuery(
            include=["error", "debug"], exclude=[], required=[]
        )

    def test_prefix_at_word_boundary_only(self):
        # Prefixes should only work at word boundaries (start of terms)
        result = parse_text_search_query("word-dash task!exclaim value+plus")
        assert result == TextSearchQuery(
            include=["word-dash", "task!exclaim", "value+plus"], exclude=[], required=[]
        )

    def test_combining_all_features(self):
        # Kitchen sink test with every feature
        result = parse_text_search_query(
            'regular "exact phrase" -excluded +"required phrase" !also_excluded more_regular'
        )
        assert result == TextSearchQuery(
            include=["regular", "exact phrase", "more_regular"],
            exclude=["excluded", "also_excluded"],
            required=["required phrase"],
        )


class TestCasePreservation:
    """Test that original case is preserved in parsed terms"""

    def test_preserves_case_in_include_terms(self):
        result = parse_text_search_query("Error WARNING Timeout")
        assert result == TextSearchQuery(
            include=["Error", "WARNING", "Timeout"], exclude=[], required=[]
        )

    def test_preserves_case_in_exclude_terms(self):
        result = parse_text_search_query("-DEBUG !TestMode")
        assert result == TextSearchQuery(
            include=[], exclude=["DEBUG", "TestMode"], required=[]
        )

    def test_preserves_case_in_quoted_phrases(self):
        result = parse_text_search_query('"Connection Timeout Error"')
        assert result == TextSearchQuery(
            include=["Connection Timeout Error"], exclude=[], required=[]
        )


class TestDataclassStructure:
    """Test the TextSearchQuery dataclass itself"""

    def test_dataclass_creation(self):
        query = TextSearchQuery(
            include=["term1", "term2"], exclude=["excluded"], required=["required"]
        )
        assert query.include == ["term1", "term2"]
        assert query.exclude == ["excluded"]
        assert query.required == ["required"]

    def test_dataclass_defaults(self):
        query = TextSearchQuery()
        assert query.include == []
        assert query.exclude == []
        assert query.required == []

    def test_dataclass_equality(self):
        query1 = TextSearchQuery(include=["test"], exclude=[], required=[])
        query2 = TextSearchQuery(include=["test"], exclude=[], required=[])
        assert query1 == query2

    def test_dataclass_repr(self):
        query = TextSearchQuery(include=["test"], exclude=["debug"], required=["error"])
        repr_str = repr(query)
        assert "include=['test']" in repr_str
        assert "exclude=['debug']" in repr_str
        assert "required=['error']" in repr_str


# Integration-style tests that verify the complete parsing flow
class TestIntegrationScenarios:
    """Test realistic query parsing scenarios end-to-end"""

    @pytest.mark.parametrize(
        "query, expected",
        [
            # Simple cases
            ("error", TextSearchQuery(include=["error"], exclude=[], required=[])),
            ("-debug", TextSearchQuery(include=[], exclude=["debug"], required=[])),
            (
                "+required",
                TextSearchQuery(include=[], exclude=[], required=["required"]),
            ),
            # Query examples
            (
                "error warning timeout",
                TextSearchQuery(
                    include=["error", "warning", "timeout"], exclude=[], required=[]
                ),
            ),
            (
                "error -debug -test",
                TextSearchQuery(
                    include=["error"], exclude=["debug", "test"], required=[]
                ),
            ),
            (
                "error !debug !test",
                TextSearchQuery(
                    include=["error"], exclude=["debug", "test"], required=[]
                ),
            ),
            (
                '"connection timeout"',
                TextSearchQuery(
                    include=["connection timeout"], exclude=[], required=[]
                ),
            ),
            (
                '"connection timeout" error -debug !test',
                TextSearchQuery(
                    include=["connection timeout", "error"],
                    exclude=["debug", "test"],
                    required=[],
                ),
            ),
            # Future AND syntax
            (
                "+error +connection -debug",
                TextSearchQuery(
                    include=[], exclude=["debug"], required=["error", "connection"]
                ),
            ),
        ],
    )
    def test_example_queries(self, query: str, expected: TextSearchQuery) -> None:
        """Test all query examples parse correctly"""
        result = parse_text_search_query(query)
        assert result == expected


class TestMultilingualSupport:
    """Test parsing with international characters and languages"""

    def test_japanese_terms(self):
        # Japanese: error, flow, test
        result = parse_text_search_query("エラー フロー -テスト")
        assert result == TextSearchQuery(
            include=["エラー", "フロー"], exclude=["テスト"], required=[]
        )

    def test_chinese_simplified_terms(self):
        # Chinese: error, connection, debug
        result = parse_text_search_query("错误 连接 -调试")
        assert result == TextSearchQuery(
            include=["错误", "连接"], exclude=["调试"], required=[]
        )

    def test_chinese_traditional_terms(self):
        # Traditional Chinese: database, timeout
        result = parse_text_search_query("資料庫 +超時")
        assert result == TextSearchQuery(
            include=["資料庫"], exclude=[], required=["超時"]
        )

    def test_cyrillic_terms(self):
        # Russian: error, flow, test
        result = parse_text_search_query("ошибка поток -тест")
        assert result == TextSearchQuery(
            include=["ошибка", "поток"], exclude=["тест"], required=[]
        )

    def test_french_with_accents(self):
        # French: error, connection, test environment
        result = parse_text_search_query('erreur connexión -"environment de tést"')
        assert result == TextSearchQuery(
            include=["erreur", "connexión"],
            exclude=["environment de tést"],
            required=[],
        )

    def test_german_compound_words(self):
        # German compound words
        result = parse_text_search_query(
            "Verbindungsfehler Datenbankzugriff -Testumgebung"
        )
        assert result == TextSearchQuery(
            include=["Verbindungsfehler", "Datenbankzugriff"],
            exclude=["Testumgebung"],
            required=[],
        )

    def test_arabic_terms(self):
        # Arabic: error, connection (right-to-left text)
        result = parse_text_search_query("خطأ اتصال")
        assert result == TextSearchQuery(
            include=["خطأ", "اتصال"], exclude=[], required=[]
        )

    def test_mixed_languages_in_query(self):
        # Mixed language query
        result = parse_text_search_query(
            'error エラー -debug -調試 +"connection établie"'
        )
        assert result == TextSearchQuery(
            include=["error", "エラー"],
            exclude=["debug", "調試"],
            required=["connection établie"],
        )

    def test_emoji_in_search_terms(self):
        # Modern usage might include emoji
        result = parse_text_search_query("🚫 error ✅ success -🐛 -bug")
        assert result == TextSearchQuery(
            include=["🚫", "error", "✅", "success"], exclude=["🐛", "bug"], required=[]
        )
