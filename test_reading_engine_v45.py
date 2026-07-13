import unittest

from reading_engine_v45 import (
    V45_RESPONSE_SCHEMA,
    V45_SYSTEM_INSTRUCTION,
    evaluate_variants_v45,
    score_variant_v45,
)
from test_reading_engine_v41 import CARDS, QUESTION, valid_payload


def two_variant_payload():
    base = valid_payload()
    text = base.pop("final_text")
    base["variants"] = [
        {"final_text": text},
        {"final_text": text.replace("Больше ясности", "Ясность")},
    ]
    return base


class ReadingEngineV45Tests(unittest.TestCase):
    def test_schema_requires_variants(self):
        self.assertIn("variants", V45_RESPONSE_SCHEMA["required"])

    def test_instruction_requests_two_distinct_versions(self):
        self.assertIn("два самостоятельных варианта", V45_SYSTEM_INSTRUCTION)
        self.assertIn("Вариант 1", V45_SYSTEM_INSTRUCTION)
        self.assertIn("Вариант 2", V45_SYSTEM_INSTRUCTION)

    def test_two_valid_variants_produce_selection(self):
        selected, issues = evaluate_variants_v45(
            two_variant_payload(), spread_type="love",
            user_question=QUESTION, cards=CARDS,
        )
        self.assertIsNotNone(selected)
        self.assertIn(selected["index"], (1, 2))
        self.assertEqual(issues, [])

    def test_one_bad_variant_does_not_force_fallback(self):
        payload = two_variant_payload()
        payload["variants"][0]["final_text"] = "Слишком коротко."
        selected, issues = evaluate_variants_v45(
            payload, spread_type="love",
            user_question=QUESTION, cards=CARDS,
        )
        self.assertEqual(selected["index"], 2)
        self.assertTrue(any(issue.startswith("variant_1:") for issue in issues))

    def test_both_bad_variants_are_rejected(self):
        payload = two_variant_payload()
        payload["variants"] = [
            {"final_text": "Коротко."},
            {"final_text": "Тоже коротко."},
        ]
        selected, issues = evaluate_variants_v45(
            payload, spread_type="love",
            user_question=QUESTION, cards=CARDS,
        )
        self.assertIsNone(selected)
        self.assertTrue(issues)

    def test_meta_disclaimer_lowers_score(self):
        clean = valid_payload()["final_text"]
        clumsy = clean.replace(
            "Вопрос о продолжении", "Только вы можете решить за вас. Вопрос о продолжении"
        )
        clean_score, _ = score_variant_v45(clean, [])
        clumsy_score, warnings = score_variant_v45(clumsy, [])
        self.assertLess(clumsy_score, clean_score)
        self.assertIn("meta_only_you", warnings)

    def test_style_issue_is_soft_not_fatal(self):
        payload = two_variant_payload()
        payload["variants"][0]["final_text"] = payload["variants"][0]["final_text"].replace(
            "Вопрос о продолжении", "Это нецелесообразно. Вопрос о продолжении"
        )
        selected, _ = evaluate_variants_v45(
            payload, spread_type="love",
            user_question=QUESTION, cards=CARDS,
        )
        self.assertIsNotNone(selected)

    def test_less_mechanical_variant_scores_higher(self):
        clean = valid_payload()["final_text"]
        mechanical = clean.replace(
            "Солнце показывает живую и открытую сторону общения, а Отшельник добавляет",
            "Солнце показывает тепло. Отшельник показывает дистанцию. Умеренность предлагает меру. Отшельник добавляет",
        )
        clean_score, _ = score_variant_v45(clean, [])
        mechanical_score, warnings = score_variant_v45(mechanical, [])
        self.assertLess(mechanical_score, clean_score)
        self.assertIn("mechanical_card_listing", warnings)


if __name__ == "__main__":
    unittest.main()
