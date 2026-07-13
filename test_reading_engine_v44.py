import unittest

from reading_engine_v44 import (
    V44_DEFAULT_SYSTEM_INSTRUCTION,
    V44_LOVE_SYSTEM_INSTRUCTION,
    validate_v44_payload,
)
from reading_engine_v42 import V42_SYSTEM_INSTRUCTION
from test_reading_engine_v41 import CARDS, QUESTION, valid_payload


class ReadingEngineV44Tests(unittest.TestCase):
    def validate(self, payload, spread_type="love"):
        return validate_v44_payload(
            payload, spread_type=spread_type,
            user_question=QUESTION, cards=CARDS,
        )

    def test_career_profile_is_frozen_v42_profile(self):
        self.assertEqual(V44_DEFAULT_SYSTEM_INSTRUCTION, V42_SYSTEM_INSTRUCTION)

    def test_love_profile_is_separate_and_compact(self):
        self.assertNotEqual(V44_LOVE_SYSTEM_INSTRUCTION, V44_DEFAULT_SYSTEM_INSTRUCTION)
        self.assertIn("взаимную инициативу", V44_LOVE_SYSTEM_INSTRUCTION)
        self.assertIn("Карты описывают ситуацию", V44_LOVE_SYSTEM_INSTRUCTION)

    def test_investing_expectations_is_rejected_for_love(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "сколько участия вы готовы вкладывать",
            "как не инвестировать все свои ожидания",
        )
        issues = self.validate(payload)
        self.assertTrue(any(issue.startswith("love_style:инвестировать") for issue in issues))

    def test_internal_balance_is_rejected_for_love(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "вопрос вашей меры", "вопрос внутреннего баланса"
        )
        self.assertTrue(any(issue.startswith("love_style:") for issue in self.validate(payload)))

    def test_love_style_filter_does_not_affect_career(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "вопрос вашей меры", "вопрос внутреннего баланса"
        )
        self.assertFalse(
            any(issue.startswith("love_style:") for issue in self.validate(payload, "career"))
        )

    def test_heavy_style_reports_actual_phrase(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Вопрос о продолжении", "Это нецелесообразно. Вопрос о продолжении"
        )
        issues = self.validate(payload, "career")
        self.assertIn("heavy_style:нецелесообразно", issues)
        self.assertNotIn("heavy_style", issues)

    def test_clean_payload_passes(self):
        self.assertEqual(self.validate(valid_payload()), [])


if __name__ == "__main__":
    unittest.main()
