import json
import unittest

from reading_engine_v4 import (
    V4_RESPONSE_SCHEMA,
    V4_SYSTEM_INSTRUCTION,
    build_local_fallback_v4,
    build_reading_v4_prompt,
    generate_reading_v4,
    parse_v4_payload,
    prepare_cards_v4,
    render_v4_payload,
    validate_v4_payload,
)


CARDS = [
    {
        "name": "Солнце",
        "general": "Тепло и ясность.",
        "love": "Тепло и открытость контакта.",
        "career": "Видимая привлекательность возможности.",
    },
    {
        "name": "Отшельник",
        "general": "Пауза и дистанция.",
        "love": "Пауза и дистанция без объяснения причин.",
        "career": "Необходимость отдельной оценки.",
    },
    {
        "name": "Умеренность",
        "general": "Мера и согласование.",
        "love": "Мера участия и подходящий формат.",
        "career": "Сопоставление условий.",
    },
]


def valid_payload():
    return {
        "direct_response": (
            "В этом вопросе решение зависит от того, сочетается ли теплота общения "
            "с достаточной для вас устойчивостью контакта."
        ),
        "facts_used": ["тепло общаемся", "надолго пропадает"],
        "unknowns_kept_open": [
            "причины пауз",
            "инициатива каждой стороны",
        ],
        "card_roles": [
            {"card": "Солнце", "role": "освещает заметное тепло общения"},
            {"card": "Отшельник", "role": "добавляет тему пауз без объяснения причин"},
            {"card": "Умеренность", "role": "возвращает вопрос к подходящей мере участия"},
        ],
        "synthesis": (
            "Солнце и Отшельник создают контраст между теплом и паузами, "
            "а Умеренность переводит его в вопрос о подходящей вам мере контакта."
        ),
        "clarity_basis": (
            "Ясность добавит наблюдение за тем, возникает ли инициатива поддерживать "
            "и возобновлять связь с обеих сторон."
        ),
        "reflection_question": (
            "Какой формат общения соответствует вашим потребностям в близости и регулярности?"
        ),
    }


class ReadingEngineV4Tests(unittest.TestCase):
    def test_schema_requires_all_structured_fields(self):
        required = set(V4_RESPONSE_SCHEMA["required"])
        self.assertIn("facts_used", required)
        self.assertIn("unknowns_kept_open", required)
        self.assertIn("card_roles", required)
        self.assertIn("synthesis", required)
        self.assertIn("reflection_question", required)

    def test_system_instruction_separates_facts_and_symbolism(self):
        self.assertIn("только короткие точные цитаты", V4_SYSTEM_INSTRUCTION)
        self.assertIn("не является фактом", V4_SYSTEM_INSTRUCTION)
        self.assertIn("Не угадывайте мысли", V4_SYSTEM_INSTRUCTION)

    def test_prompt_contains_question_cards_and_positions(self):
        question = "Мы тепло общаемся, но потом он надолго пропадает."
        prompt = build_reading_v4_prompt("love", question, CARDS, "love")
        self.assertIn(question, prompt)
        for card in CARDS:
            self.assertIn(card["name"], prompt)
        self.assertIn("Что непосредственно видно в контакте", prompt)
        self.assertIn("Верните только JSON", prompt)

    def test_topic_meanings_are_prepared(self):
        prepared = prepare_cards_v4(CARDS, "love", "love")
        self.assertEqual(prepared[0]["meaning"], CARDS[0]["love"])
        self.assertEqual(prepared[2]["name"], "Умеренность")

    def test_valid_payload_passes_validation(self):
        issues = validate_v4_payload(
            valid_payload(),
            user_question=(
                "Мы тепло общаемся, но потом он надолго пропадает. "
                "Стоит ли продолжать этот контакт?"
            ),
            cards=CARDS,
        )
        self.assertEqual(issues, [])

    def test_fact_must_be_exact_fragment_of_question(self):
        payload = valid_payload()
        payload["facts_used"].append("у нас редкие встречи")
        issues = validate_v4_payload(
            payload,
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
        )
        self.assertIn("unsupported_fact", issues)

    def test_all_card_roles_are_required(self):
        payload = valid_payload()
        payload["card_roles"] = payload["card_roles"][:2]
        issues = validate_v4_payload(
            payload,
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
        )
        self.assertIn("card_roles_mismatch", issues)

    def test_synthesis_must_name_all_cards(self):
        payload = valid_payload()
        payload["synthesis"] = "Солнце и Отшельник образуют контраст."
        issues = validate_v4_payload(
            payload,
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
        )
        self.assertIn("synthesis_missing_cards", issues)

    def test_high_risk_motive_triggers_validation(self):
        payload = valid_payload()
        payload["synthesis"] = (
            "Солнце, Отшельник и Умеренность показывают, что он хочет побыть один."
        )
        issues = validate_v4_payload(
            payload,
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
        )
        self.assertIn("high_risk_claim", issues)

    def test_high_risk_directive_triggers_validation(self):
        payload = valid_payload()
        payload["clarity_basis"] = "Вам необходимо продолжать этот контакт."
        issues = validate_v4_payload(
            payload,
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
        )
        self.assertIn("high_risk_claim", issues)

    def test_greeting_triggers_validation(self):
        payload = valid_payload()
        payload["direct_response"] = "Приветствую. Решение зависит от устойчивости контакта."
        issues = validate_v4_payload(
            payload,
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
        )
        self.assertIn("greeting", issues)

    def test_reflection_must_be_a_question(self):
        payload = valid_payload()
        payload["reflection_question"] = "Определите подходящий формат."
        issues = validate_v4_payload(
            payload,
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
        )
        self.assertIn("reflection_not_question", issues)

    def test_parser_rejects_malformed_json(self):
        payload, issues = parse_v4_payload("{bad json")
        self.assertIsNone(payload)
        self.assertEqual(issues, ["invalid_json"])

    def test_renderer_creates_three_paragraphs(self):
        text = render_v4_payload(valid_payload())
        self.assertEqual(len(text.split("\n\n")), 3)
        self.assertTrue(text.endswith("?"))

    def test_renderer_only_removes_markdown_stars(self):
        payload = valid_payload()
        payload["direct_response"] = "**Первый ответ.**"
        payload["synthesis"] = "*Связный синтез.*"
        text = render_v4_payload(payload)
        self.assertTrue(text.startswith("Первый ответ."))
        self.assertIn("Связный синтез.", text)

    def test_invalid_payload_uses_fallback_without_second_call(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            payload = valid_payload()
            payload["facts_used"] = ["придуманный факт"]
            return json.dumps(payload, ensure_ascii=False)

        result = generate_reading_v4(
            spread_type="love",
            user_question="Мы тепло общаемся, но потом он надолго пропадает.",
            cards=CARDS,
            topic="love",
            ai_call=fake_ai,
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["used_fallback"])
        self.assertIn("unsupported_fact", result["issues"])
        self.assertIn("Солнце", result["text"])
        self.assertIn("Умеренность", result["text"])

    def test_valid_generation_uses_ai_components(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return json.dumps(valid_payload(), ensure_ascii=False)

        result = generate_reading_v4(
            spread_type="love",
            user_question=(
                "Мы тепло общаемся, но потом он надолго пропадает. "
                "Стоит ли продолжать этот контакт?"
            ),
            cards=CARDS,
            topic="love",
            ai_call=fake_ai,
        )
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["text"].split("\n\n")), 3)

    def test_empty_answer_uses_fallback_without_retry(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return None

        result = generate_reading_v4(
            spread_type="career",
            user_question="Соглашаться на предложение?",
            cards=CARDS,
            topic="career",
            ai_call=fake_ai,
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["issues"], ["empty_ai_answer"])

    def test_love_fallback_does_not_decide_for_user(self):
        text = build_local_fallback_v4(
            spread_type="love",
            user_question="Продолжать контакт?",
            cards=CARDS,
            topic="love",
        )
        self.assertNotIn("продолжать стоит", text.lower())
        self.assertIn("взаимность", text)
        self.assertTrue(text.endswith("?"))

    def test_career_fallback_focuses_on_role_information(self):
        text = build_local_fallback_v4(
            spread_type="career",
            user_question="Соглашаться?",
            cards=CARDS,
            topic="career",
        )
        self.assertIn("обязанности", text)
        self.assertIn("полномочия", text)
        self.assertNotIn("соглашайтесь", text.lower())


if __name__ == "__main__":
    unittest.main()
