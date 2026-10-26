"""The v5-vi rules the validator adds: honest diacritics flag, cross-set overlap, lang.""" 

from __future__ import annotations

from research import validate_eval_set as v


def _negative(**overrides) -> dict:
    question = {"id": "Q1", "q": "tat arming check nhu the nao", "lang": "vi",
                "category": "negative", "expect_none": True}
    question.update(overrides)
    return question


def test_no_diacritics_question_is_accepted():
    report = v.validate([_negative(diacritics=False)], None, strict_v5=True)
    assert report["errors"] == []
    assert report["diacritics_false"] == 1


def test_diacritics_flag_on_a_marked_question_is_an_error():
    report = v.validate([_negative(q="tắt arming check", diacritics=False)], None, strict_v5=True)
    assert [error["code"] for error in report["errors"]] == ["diacritics_flag_wrong"]


def test_v5_rejects_an_english_question():
    report = v.validate([_negative(lang="en")], None, strict_v5=True)
    assert [error["code"] for error in report["errors"]] == ["v5_lang_must_be_vi_or_mixed"]


def test_cross_overlap_flags_a_paraphrase_of_a_v4_question():
    questions = [{"id": "A", "q": "cach chinh toc do bay trong loiter mode"}]
    others = [("eval_v4_dev.yaml", {"id": "B", "q": "chinh toc do bay loiter mode"})]
    errors = v.cross_overlap_errors(questions, others)
    assert [error["code"] for error in errors] == ["overlaps_v4"]
    assert errors[0]["detail"].startswith("B@eval_v4_dev.yaml")


def test_cross_overlap_ignores_an_identifier_only_query_and_a_different_topic():
    questions = [{"id": "A", "q": "AP_RCProtocol_CRSF"},
                 {"id": "B", "q": "cach chinh toc do bay trong loiter mode"}]
    others = [("eval_v4_dev.yaml", {"id": "C", "q": "AP_RCProtocol_CRSF"}),
              ("eval_v4_dev.yaml", {"id": "D", "q": "pinout cua matek h743"})]
    assert v.cross_overlap_errors(questions, others) == []
