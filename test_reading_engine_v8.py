import json
import unittest

from reading_engine_v8 import (
    FINAL_SCHEMA_V8,
    MODEL_NAME_V8,
    SYSTEM_PROMPT_V8,
    build_prompt_v8,
    calculate_cost_v8,
    clean_stars_v8,
    generate_reading_v8,
    hard_safety_issues_v8,
    validate_final_v8,
)


INITIATIVE_QUESTION = "Выйдет тот, о ком я думаю постоянно, первым на контакт?"
INITIATIVE_CARDS = [
    {"name": "Колесница", "general": "Инициатива без доказательства намерения."},
    {"name": "Башня", "general": "Противоречие, нарушающее прямое движение."},
    {"name": "Звезда", "general": "Надежда без подтверждённого действия."},
]

CHOICE_QUESTION = (
    "Мы тепло общаемся, но потом он надолго пропадает. "
    "Стоит ли продолжать этот контакт?"
)
CHOICE_CARDS = [
    {"name": "Солнце", "love": "Теплота общения."},
    {"name": "Отшельник", "love": "Дистанция и паузы."},
    {"name": "Умеренность", "love": "Подходящая мера участия."},
]

VALID_INITIATIVE_TEXT = """По символике этого сочетания уверенного указания на первый шаг с его стороны нет, хотя возможность контакта остаётся открытой. Карты не закрывают развитие общения, но пока не показывают его как уже определившееся событие. Поэтому надежда здесь заметнее, чем конкретное подтверждение будущего контакта.

Колесница вносит тему движения и инициативы, однако Башня резко нарушает прямое развитие этого импульса. Звезда сохраняет надежду, но не превращает её в конкретное действие. Вместе карты показывают возможность, которой пока не хватает подтверждения в реальном общении.

В вашем вопросе заметно, как много внимания занимает ожидание контакта. Пока реального шага нет, неопределённость остаётся частью самой ситуации. Что помогло бы вам отличить открытую возможность от надежды, которая пока ничем не подтверждена?"""

VALID_CHOICE_TEXT = """Этот контакт может оставаться ценным, но решение зависит не только от теплоты общения, а и от того, насколько его прерывистый ритм подходит вам. В ситуации одновременно присутствуют близость и отсутствие устойчивости, и обе стороны имеют значение для вашего выбора.

Солнце подчёркивает радость и открытость ваших разговоров, Отшельник добавляет к ним дистанцию и долгие паузы, а Умеренность связывает эти стороны через поиск подходящей меры участия. Вместе карты показывают, что приятные моменты и регулярность связи — разные качества контакта.

Расклад не предлагает готового решения и не объясняет причины чужого молчания. Он помогает сопоставить разные стороны происходящего, не обесценивая приятные моменты и не скрывая цену пауз. Какая взаимность и частота общения нужны вам, чтобы продолжение этого контакта ощущалось ценным?"""


class PromptTests(unittest.TestCase):
    def test_one_call_system_requests_ready_text(self):
        self.assertIn("сразу написать готовый ответ", SYSTEM_PROMPT_V8)
        self.assertIn("не показывай служебный анализ", SYSTEM_PROMPT_V8)
        self.assertIn("подменять вопрос о чужой инициативе", SYSTEM_PROMPT_V8)

    def test_schema_has_only_final_text(self):
        self.assertEqual(FINAL_SCHEMA_V8["required"], ["final_text"])
        self.assertFalse(FINAL_SCHEMA_V8["additionalProperties"])

    def test_prompt_contains_question_cards_positions_and_meanings(self):
        prompt = build_prompt_v8(
            INITIATIVE_QUESTION,
            INITIATIVE_CARDS,
            "initiative",
        )
        self.assertIn(INITIATIVE_QUESTION, prompt)
        for card in INITIATIVE_CARDS:
            self.assertIn(card["name"], prompt)
            self.assertIn(card["general"], prompt)
        self.assertIn("Правило этого маршрута", prompt)

    def test_initiative_prompt_forbids_redirect_to_user(self):
        prompt = build_prompt_v8(
            INITIATIVE_QUESTION,
            INITIATIVE_CARDS,
            "initiative",
        )
        self.assertIn("Не переходи к возможности инициативы пользователя", prompt)

    def test_love_prompt_does_not_require_accepting_bad_rhythm(self):
        prompt = build_prompt_v8(
            CHOICE_QUESTION,
            CHOICE_CARDS,
            "personal_choice",
            "love",
        )
        self.assertIn("не предлагай терпеть или принимать неудобный ритм", prompt)


class ValidationTests(unittest.TestCase):
    def test_valid_initiative_text_passes(self):
        issues, warnings = validate_final_v8(
            {"final_text": VALID_INITIATIVE_TEXT},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])

    def test_valid_choice_text_passes(self):
        issues, warnings = validate_final_v8(
            {"final_text": VALID_CHOICE_TEXT},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
            route="personal_choice",
        )
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])

    def test_missing_card_is_rejected(self):
        text = VALID_INITIATIVE_TEXT.replace("Звезда", "последняя карта")
        issues, _ = validate_final_v8(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("final_missing_cards:Звезда", issues)

    def test_two_questions_are_rejected(self):
        text = VALID_CHOICE_TEXT.replace(
            "Расклад не предлагает",
            "Стоит ли продолжать этот контакт? Расклад не предлагает",
        )
        issues, _ = validate_final_v8(
            {"final_text": text},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
            route="personal_choice",
        )
        self.assertIn("question_count:2", issues)

    def test_user_initiative_shift_is_rejected(self):
        text = VALID_INITIATIVE_TEXT.replace(
            "Карты не закрывают развитие общения",
            "Возможна ваша собственная инициатива. Карты не закрывают развитие общения",
        )
        issues, _ = validate_final_v8(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("initiative_shift_to_user", issues)

    def test_mind_reading_is_rejected(self):
        self.assertIn("unsafe:mind_reading", hard_safety_issues_v8("Он хочет написать первым."))

    def test_certain_future_is_rejected(self):
        self.assertIn("unsafe:certain_future", hard_safety_issues_v8("Он обязательно выйдет на связь."))

    def test_probability_language_is_allowed(self):
        self.assertEqual(
            hard_safety_issues_v8("Возможно, человек выйдет на связь, но карты этого не гарантируют."),
            [],
        )

    def test_unexpected_field_is_rejected(self):
        issues, _ = validate_final_v8(
            {"final_text": VALID_INITIATIVE_TEXT, "analysis": "hidden"},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("unexpected_fields:analysis", issues)

    def test_cleanup_removes_only_markdown_stars(self):
        source = "**Колесница** сохраняет текст, а *Звезда* — надежду."
        self.assertEqual(
            clean_stars_v8(source),
            "Колесница сохраняет текст, а Звезда — надежду.",
        )


class CostTests(unittest.TestCase):
    def test_terra_cost_includes_cached_input_and_output(self):
        cost = calculate_cost_v8(
            {
                "input_tokens": 2000,
                "cached_input_tokens": 500,
                "output_tokens": 200,
                "reasoning_tokens": 50,
            },
            MODEL_NAME_V8,
        )
        expected = (1500 * 2.00 + 500 * 0.20 + 200 * 12.00) / 1_000_000
        self.assertAlmostEqual(cost, expected)

    def test_reasoning_is_not_double_charged(self):
        plain = calculate_cost_v8(
            {"input_tokens": 1000, "output_tokens": 300, "reasoning_tokens": 0}
        )
        reasoned = calculate_cost_v8(
            {"input_tokens": 1000, "output_tokens": 300, "reasoning_tokens": 200}
        )
        self.assertEqual(plain, reasoned)

    def test_unknown_model_has_no_estimate(self):
        self.assertIsNone(
            calculate_cost_v8({"input_tokens": 100, "output_tokens": 100}, "unknown")
        )


class OrchestrationTests(unittest.TestCase):
    def test_success_uses_exactly_one_call(self):
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return {
                "payload": {"final_text": VALID_INITIATIVE_TEXT},
                "status": "completed",
                "model": MODEL_NAME_V8,
                "usage": {"input_tokens": 1800, "output_tokens": 220},
            }

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["ai_requests"], 1)
        self.assertFalse(result["used_fallback"])
        self.assertIsNotNone(result["diagnostics"]["cost_usd"])

    def test_json_string_reply_uses_one_call(self):
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return json.dumps({"final_text": VALID_INITIATIVE_TEXT}, ensure_ascii=False)

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["used_fallback"])

    def test_invalid_json_falls_back_without_retry(self):
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return "{"

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "generation")

    def test_unsafe_text_falls_back_without_retry(self):
        unsafe = VALID_INITIATIVE_TEXT.replace(
            "Карты не закрывают развитие общения",
            "Он хочет написать первым. Карты не закрывают развитие общения",
        )
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return {"payload": {"final_text": unsafe}}

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["used_fallback"])
        self.assertIn("unsafe:mind_reading", result["issues"])

    def test_unsupported_route_makes_no_call(self):
        calls = []
        result = generate_reading_v8(
            question="Расскажите об этом раскладе.",
            cards=INITIATIVE_CARDS,
            model_call=lambda prompt: calls.append(prompt),
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["ai_requests"], 0)
        self.assertTrue(result["used_fallback"])


if __name__ == "__main__":
    unittest.main()
