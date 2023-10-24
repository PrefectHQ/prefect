from prefect.utilities.text import HELP_TEXT, truncated_to


class TestTruncatedTo:
    def test_empty_value(self):
        value = None
        length = 100
        trunc = truncated_to(length, value)
        assert trunc == ""

    def test_length_exceeds_value(self):
        value = "a" * 50
        length = 51
        trunc = truncated_to(length, value)
        assert trunc == value

    def test_normal_truncation(self):
        value = "a" * 100
        length = 50
        trunc = truncated_to(length, value)
        assert len(trunc) == length
        assert trunc.endswith(HELP_TEXT)

    def test_truncation_help_text_too_long(self):
        value = "a" * 100
        length = 10
        trunc = truncated_to(length, value)
        assert len(trunc) == length
        assert trunc == "a" * length
