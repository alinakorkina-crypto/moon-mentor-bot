import json
import unittest

from reading_engine_v41 import (
    V41_RESPONSE_SCHEMA,
    V41_SYSTEM_INSTRUCTION,
    build_reading_v41_prompt,
    clean_final_text_v41,
    generate_reading_v41,
    validate_v41_payload,
)


CARDS = [
    {"name": "Солнце", "general": "Тепло.", "love": "Тепло контакта."},
    {"name": "Отшельник", "general": "Пауза.", "love": "Дистанция без объяснения причин."},
    {"name": "Умеренность", "general": "Мера.", "love": "Подходящая мера участия."},
]
QUESTION = "Мы тепло общаемся, но потом он надолго пропадает. Стоит ли продолжать этот контакт?"


def valid_payload():
    return {
        "facts_used": ["тепло общаемся", "надолго пропадает"],
        "unknowns_kept_open": ["причины пауз"],
        "card_roles": [
            {"card": "Солнце", "role": "тепло контакта"},
            {"card": "Отшельник", "role": "пауза в контакте"},
            {"card": "Умеренность", "role": "личная мера участия"},
        ],
        "final_text": (
            "Вопрос о продолжении этого контакта связан с тем, насколько вам подходит его "
            "нынешний ритм. Тепло в общении заметно, но рядом с ним остаются долгие паузы, "
            "поэтому важны не только яркие встречи, но и устойчивость связи.\n\n"
            "Солнце показывает живую и открытую сторону общения, а Отшельник добавляет к "
            "ней дистанцию. Умеренность не отменяет этот контраст, а помогает увидеть в нём "
            "вопрос вашей меры: сколько участия вы готовы вкладывать, когда близость и тишина "
            "регулярно сменяют друг друга.\n\n"
            "Больше ясности даст не объяснение причин исчезновения, а наблюдение за взаимностью: "
            "возникает ли желание возобновлять связь с обеих сторон и сохраняется ли интерес "
            "между паузами. Какой ритм общения позволяет вам чувствовать и тепло, и устойчивость?"
        ),
    }


class ReadingEngineV41Tests(unittest.TestCase):
    def test_schema_contains_analysis_and_complete_text(self):
        self.assertEqual(
            set(V41_RESPONSE_SCHEMA["required"]),
            {"facts_used", "unknowns_kept_open", "card_roles", "final_text"},
        )

    def test_instruction_requests_natural_complete_text(self):
        self.assertIn("готовый ответ пользователю", V41_SYSTEM_INSTRUCTION)
        self.assertIn("ровно 3 коротких абзаца", V41_SYSTEM_INSTRUCTION)
        self.assertIn("не принимает решение", V41_SYSTEM_INSTRUCTION)

    def test_prompt_contains_question_positions_and_all_cards(self):
        prompt = build_reading_v41_prompt("love", QUESTION, CARDS, "love")
        self.assertIn(QUESTION, prompt)
        for card in CARDS:
            self.assertIn(card["name"], prompt)
        self.assertIn("Что непосредственно видно в контакте", prompt)

    def test_valid_payload_passes(self):
        self.assertEqual(
            validate_v41_payload(valid_payload(), user_question=QUESTION, cards=CARDS),
            [],
        )

    def test_fact_must_be_from_question(self):
        payload = valid_payload()
        payload["facts_used"].append("он возвращается первым")
        self.assertIn(
            "unsupported_fact",
            validate_v41_payload(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_card_roles_must_cover_every_card(self):
        payload = valid_payload()
        payload["card_roles"].pop()
        self.assertIn(
            "card_roles_mismatch",
            validate_v41_payload(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_final_text_must_name_every_card(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace("Умеренность", "Третья карта")
        self.assertIn(
            "final_text_missing_cards",
            validate_v41_payload(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_heavy_style_is_rejected(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Вопрос о продолжении", "Для вашего благополучия вопрос о продолжении"
        )
        self.assertIn(
            "heavy_style",
            validate_v41_payload(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_motive_claim_is_rejected(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace(
            "Тепло в общении заметно", "Он хочет быть ближе. Тепло в общении заметно"
        )
        self.assertIn(
            "high_risk_claim",
            validate_v41_payload(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_three_paragraphs_are_required(self):
        payload = valid_payload()
        payload["final_text"] = payload["final_text"].replace("\n\n", " ")
        self.assertIn(
            "paragraph_count",
            validate_v41_payload(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_cleaning_only_removes_markdown_stars(self):
        self.assertEqual(clean_final_text_v41("**Тепло** и *пауза*."), "Тепло и пауза.")

    def test_valid_generation_uses_complete_ai_text_once(self):
        calls = []
        def fake_ai(prompt):
            calls.append(prompt)
            return json.dumps(valid_payload(), ensure_ascii=False)
        result = generate_reading_v41(
            spread_type="love", user_question=QUESTION, cards=CARDS,
            topic="love", ai_call=fake_ai,
        )
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["text"], valid_payload()["final_text"])

    def test_invalid_generation_falls_back_without_retry(self):
        calls = []
        def fake_ai(prompt):
            calls.append(prompt)
            payload = valid_payload()
            payload["facts_used"] = ["выдуманный факт"]
            return json.dumps(payload, ensure_ascii=False)
        result = generate_reading_v41(
            spread_type="love", user_question=QUESTION, cards=CARDS,
            topic="love", ai_call=fake_ai,
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["used_fallback"])
        self.assertIn("unsupported_fact", result["issues"])


if __name__ == "__main__":
    unittest.main()
