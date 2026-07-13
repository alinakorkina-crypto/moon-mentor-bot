import unittest

from reading_engine_v42 import (
    card_name_pattern_v42,
    missing_card_names_v42,
    validate_v42_payload,
)
from test_reading_engine_v41 import CARDS, QUESTION, valid_payload


class ReadingEngineV42Tests(unittest.TestCase):
    def test_case_forms_of_relationship_cards_are_accepted(self):
        text = "Солнца, Отшельника и Умеренности"
        self.assertEqual(missing_card_names_v42(text, CARDS), [])

    def test_case_forms_of_career_cards_are_accepted(self):
        cards = [
            {"name": "Колесница"},
            {"name": "Луна"},
            {"name": "Император"},
        ]
        text = "Импульс Колесницы проходит через туман Луны к структуре Императора."
        self.assertEqual(missing_card_names_v42(text, cards), [])

    def test_exact_names_are_still_accepted(self):
        text = "Солнце соединяется с Отшельником через Умеренность."
        self.assertEqual(missing_card_names_v42(text, CARDS), [])

    def test_absent_card_is_reported_by_name(self):
        missing = missing_card_names_v42("Солнце и Отшельник.", CARDS)
        self.assertEqual(missing, ["Умеренность"])

    def test_validator_reports_specific_missing_cards(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace("Умеренность", "Баланс")
        issues = validate_v42_payload(payload, user_question=QUESTION, cards=CARDS)
        self.assertIn("missing_cards:Умеренность", issues)
        self.assertNotIn("final_text_missing_cards", issues)

    def test_validator_accepts_declined_names(self):
        payload = valid_payload()
        payload["final_text"] = (
            payload["final_text"]
            .replace("Солнце", "Солнца")
            .replace("Отшельник", "Отшельника")
            .replace("Умеренность", "Умеренности")
        )
        self.assertEqual(
            validate_v42_payload(payload, user_question=QUESTION, cards=CARDS),
            [],
        )

    def test_multiword_card_pattern_handles_declension(self):
        pattern = card_name_pattern_v42("Верховная Жрица")
        self.assertRegex("урок Верховной Жрицы", pattern)


if __name__ == "__main__":
    unittest.main()
