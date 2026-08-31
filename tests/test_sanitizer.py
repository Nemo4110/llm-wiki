"""Tests for cross-platform filename sanitization (P0: sanitizer)."""

import pytest

from llm_wiki.sanitizer import sanitize_title_stem


class TestIllegalCharacters:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("LoRA: Low-Rank Adaptation", "LoRA-Low-Rank-Adaptation"),
            ("A/B testing", "A-B-testing"),
            ("what? why! ok.", "what-why!-ok"),
            ('quote "inside" star* pipe| lt< gt>', "quote-inside-star-pipe-lt-gt"),
            ("back\\slash", "backslash"),
        ],
    )
    def test_illegal_chars_removed_and_separators_dashed(self, raw, expected):
        assert sanitize_title_stem(raw) == expected

    def test_control_characters_removed(self):
        assert sanitize_title_stem("a\x00b\x1fc") == "abc"

    def test_result_has_no_windows_illegal_chars(self):
        result = sanitize_title_stem('a/b\\c:d*e?f"g<h>i|j')
        for ch in '/\\:*?"<>|':
            assert ch not in result


class TestDiacritics:
    def test_diacritics_stripped(self):
        assert sanitize_title_stem("Café Müller") == "Cafe-Muller"

    def test_cjk_preserved(self):
        assert sanitize_title_stem("深入理解 大模型") == "深入理解-大模型"

    def test_mixed_cjk_and_diacritics(self):
        assert sanitize_title_stem("深度学习 Café") == "深度学习-Cafe"


class TestReservedNames:
    @pytest.mark.parametrize(
        "name", ["CON", "con", "PRN", "AUX", "NUL", "COM1", "com7", "LPT3"]
    )
    def test_windows_reserved_names_escaped(self, name):
        result = sanitize_title_stem(name)
        assert result != name
        assert result.upper().startswith(name.upper())

    def test_non_reserved_prefix_ok(self):
        assert sanitize_title_stem("CONSOLE") == "CONSOLE"


class TestEdgeShapes:
    def test_trailing_dots_and_spaces_removed(self):
        assert sanitize_title_stem("name...   ") == "name"

    def test_all_dots_falls_back(self):
        assert sanitize_title_stem("...") == "untitled"

    def test_empty_falls_back(self):
        assert sanitize_title_stem("   ") == "untitled"

    def test_dash_runs_collapsed(self):
        assert sanitize_title_stem("a - b") == "a-b"

    def test_leading_trailing_dashes_stripped(self):
        assert sanitize_title_stem("-lead and trail-") == "lead-and-trail"


class TestByteTruncation:
    def test_ascii_truncated_to_max_bytes(self):
        result = sanitize_title_stem("word " * 100, max_bytes=50)
        assert len(result.encode("utf-8")) <= 50

    def test_truncation_backtracks_to_word_boundary(self):
        result = sanitize_title_stem("alpha beta gammadeltaepsilon zeta", max_bytes=20)
        assert result == "alpha-beta"

    def test_cjk_never_split_mid_character(self):
        result = sanitize_title_stem("深" * 100, max_bytes=50)
        # 每个 CJK 字符 3 字节;50 字节最多容纳 16 个
        assert len(result.encode("utf-8")) <= 50
        assert result == "深" * 16

    def test_truncation_strips_trailing_dash(self):
        result = sanitize_title_stem("aaaa bbbb cccc", max_bytes=10)
        assert not result.endswith("-")

    def test_default_max_bytes(self):
        result = sanitize_title_stem("x " * 500)
        assert len(result.encode("utf-8")) <= 120

    def test_short_title_untouched(self):
        assert sanitize_title_stem("LoRA", max_bytes=120) == "LoRA"
