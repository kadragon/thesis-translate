"""Tests for source/translation block alignment checks."""

import pytest

from src.core.alignment import (
    find_figure_ref_mismatches,
    find_length_outliers,
    find_misalignments,
    find_number_mismatches,
    find_term_violations,
    find_untranslated,
    interleave,
    load_terms,
    read_blocks,
)


def test_read_blocks_returns_stripped_non_empty_lines(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("  p.1\n\n  Body one.\n\n\n  Body two.\n\n", encoding="utf-8")

    assert read_blocks(str(path)) == ["p.1", "Body one.", "Body two."]


def test_find_misalignments_accepts_matching_structure():
    source = ["Title", "p.1", "A.", "B.", "p.2", "C."]
    translation = ["제목", "p.1", "가.", "나.", "p.2", "다."]

    assert find_misalignments(source, translation) == []


def test_find_misalignments_reports_page_with_missing_paragraph():
    source = ["p.1", "A.", "B.", "p.2", "C."]
    translation = ["p.1", "가.", "p.2", "다."]

    assert find_misalignments(source, translation) == [
        "p.1: source has 2 paragraphs, translation has 1"
    ]


def test_find_misalignments_reports_paragraphs_before_first_marker():
    source = ["Title", "p.1", "A."]
    translation = ["p.1", "가."]

    assert find_misalignments(source, translation) == [
        "(before first page marker): source has 1 paragraphs, translation has 0"
    ]


def test_find_misalignments_reports_marker_sequence_mismatch():
    source = ["p.1", "A.", "p.2", "B."]
    translation = ["p.1", "가.", "p.3", "나."]

    assert find_misalignments(source, translation) == [
        "page markers differ: source [p.1, p.2], translation [p.1, p.3]"
    ]


def test_find_untranslated_lists_blocks_without_hangul():
    translation = ["p.1", "가.", "Alicia M. Pike Lacy, PhD", "p.2", "Not translated."]

    assert find_untranslated(translation) == [
        "p.1 #2: Alicia M. Pike Lacy, PhD",
        "p.2 #1: Not translated.",
    ]


def test_find_length_outliers_flags_suspiciously_short_translation():
    long_source = "Word " * 60
    translation_ok = "가" * 150
    translation_short = "가" * 20
    source = ["p.1", long_source, long_source]
    translation = ["p.1", translation_ok, translation_short]

    assert find_length_outliers(source, translation) == [
        f"p.1 #2: ratio 0.07: {long_source[:60]}"
    ]


def test_find_length_outliers_ignores_short_source_paragraphs():
    source = ["p.1", "Figure 1: A caption."]
    translation = ["p.1", "그림 1"]

    assert find_length_outliers(source, translation) == []


def test_find_number_mismatches_accepts_preserved_numbers_and_citations():
    source = ["p.1", "Accuracy rose 12.5% in 2020 [3] (Smith, 2019)."]
    translation = ["p.1", "2020년 정확도가 12.5% 올랐다[3](Smith, 2019)."]

    assert find_number_mismatches(source, translation) == []


def test_find_number_mismatches_reports_missing_and_extra_numbers():
    source = ["p.1", "Fine.", "We used 1,024 samples and 3 seeds [7]."]
    translation = ["p.1", "좋다.", "1,000개 표본과 시드 3개를 썼다[7]."]

    assert find_number_mismatches(source, translation) == [
        "p.1 #2: missing [1,024], extra [1,000]: We used 1,024 samples and 3 seeds [7]."
    ]


def test_find_number_mismatches_ignores_spelled_out_numbers_written_as_digits():
    source = ["p.1", "Twenty tasks with ten classes each."]
    translation = ["p.1", "클래스 10개로 된 과제 20개."]

    assert find_number_mismatches(source, translation) == []


def test_find_figure_ref_mismatches_handles_roman_and_uppercase_refs():
    source = ["p.1", "TABLE III: Results (see FIG. 4).", "As Table IV shows."]
    translation = ["p.1", "표 III: 결과(그림 4 참조).", "Table IV에서 보듯이."]

    assert find_figure_ref_mismatches(source, translation) == [
        "p.1 #2: 표 IV 없음: As Table IV shows."
    ]


def test_find_figure_ref_mismatches_does_not_match_longer_roman_numeral():
    source = ["p.1", "Table I lists them."]
    translation = ["p.1", "표 II에 정리하였다."]

    assert find_figure_ref_mismatches(source, translation) == [
        "p.1 #1: 표 I 없음: Table I lists them."
    ]


def test_find_figure_ref_mismatches_requires_korean_figure_and_table_refs():
    source = ["p.1", "See Fig. 2 and Table 1.", "Figure 3 shows it."]
    translation = ["p.1", "그림 2와 표 1을 보라.", "Figure 3은 이를 보여 준다."]

    assert find_figure_ref_mismatches(source, translation) == [
        "p.1 #2: 그림 3 없음: Figure 3 shows it."
    ]


def test_find_term_violations_reports_missing_korean_term():
    terms = [{"term": "unlearning", "translation": "언러닝"}]
    source = ["p.1", "Machine unlearning works.", "Unlearning methods vary.", "Other."]
    translation = ["p.1", "머신 언러닝은 작동한다.", "망각 기법은 다양하다.", "기타."]

    assert find_term_violations(source, translation, terms) == [
        "p.1 #2: unlearning → 언러닝 없음: Unlearning methods vary."
    ]


def test_find_term_violations_matches_plural_but_not_substrings():
    terms = [{"term": "model", "translation": "모델"}]
    source = ["p.1", "Two models.", "A modeling tool."]
    translation = ["p.1", "두 가지.", "도구."]

    assert find_term_violations(source, translation, terms) == [
        "p.1 #1: model → 모델 없음: Two models."
    ]


def test_load_terms_merges_existing_files_and_skips_missing(tmp_path):
    first = tmp_path / "glossary.json"
    first.write_text('[{"term": "a", "translation": "가"}]', encoding="utf-8")
    second = tmp_path / "paper_terms.json"
    second.write_text('[{"term": "b", "translation": "나"}]', encoding="utf-8")

    assert load_terms([first, tmp_path / "missing.json", second]) == [
        {"term": "a", "translation": "가"},
        {"term": "b", "translation": "나"},
    ]


def test_load_terms_rejects_malformed_entries(tmp_path):
    bad = tmp_path / "terms.json"
    bad.write_text('[{"term": "a"}]', encoding="utf-8")

    with pytest.raises(ValueError, match=r"terms\.json"):
        load_terms([bad])


def test_interleave_pairs_source_and_translation_under_page_markers():
    source = ["Title", "p.1", "A.", "B."]
    translation = ["제목", "p.1", "가.", "나."]

    assert interleave(source, translation) == [
        ["Title", "제목"],
        ["p.1"],
        ["A.", "가."],
        ["B.", "나."],
    ]
