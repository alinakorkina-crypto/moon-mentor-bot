import unittest

from reading_engine_v43 import V43_SYSTEM_INSTRUCTION, validate_v43_payload
from test_reading_engine_v41 import CARDS, QUESTION, valid_payload


class ReadingEngineV43Tests(unittest.TestCase):
    def validate(self, payload, spread_type="love", question=QUESTION):
        return validate_v43_payload(
            payload, spread_type=spread_type,
            user_question=question, cards=CARDS,
        )

    def test_relationship_instruction_forbids_personifying_cards(self):
        self.assertIn("карта описывает ракурс ситуации", V43_SYSTEM_INSTRUCTION)
        self.assertIn("взаимная инициатива", V43_SYSTEM_INSTRUCTION)
        self.assertIn("не предлагайте принять", V43_SYSTEM_INSTRUCTION)

    def test_unprompted_psychological_language_is_rejected(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Тепло в общении заметно", "Тревога в общении заметна"
        )
        self.assertIn("love_psychologizing", self.validate(payload))

    def test_user_word_is_not_rejected_when_present_in_question(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Тепло в общении заметно", "Тревога в общении заметна"
        )
        issues = self.validate(payload, question=QUESTION + " Я чувствую тревогу.")
        self.assertNotIn("love_psychologizing", issues)

    def test_advice_to_accept_format_is_rejected(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Вопрос о продолжении", "Важно принять такой формат. Вопрос о продолжении"
        )
        self.assertIn("love_acceptance_advice", self.validate(payload))

    def test_card_personification_is_rejected(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Отшельник добавляет к ней дистанцию",
            "Отшельник уходит в тень и держит дистанцию",
        )
        self.assertIn("card_personification", self.validate(payload))

    def test_career_does_not_receive_love_style_filter(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Тепло в общении заметно", "Тревога в общении заметна"
        )
        self.assertNotIn("love_psychologizing", self.validate(payload, spread_type="career"))

    def test_clean_relationship_payload_still_passes(self):
        self.assertEqual(self.validate(valid_payload()), [])


if __name__ == "__main__":
    unittest.main()
