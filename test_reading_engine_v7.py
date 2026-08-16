import json
import unittest

from reading_engine_v7 import (
    ANALYSIS_SCHEMA_V7,
    ANALYSIS_SYSTEM_V7,
    EDITOR_SYSTEM_V7,
    build_analysis_prompt_v7,
    build_editor_prompt_v7,
    clean_stars_v7,
    generate_reading_v7,
    hard_safety_issues_v7,
    style_warnings_v7,
    validate_analysis_v7,
    validate_final_v7,
)


INITIATIVE_QUESTION = "Выйдет тот, о ком я думаю постоянно, первым на контакт?"
INITIATIVE_CARDS = [
    {
        "name": "Колесница",
        "general": "Инициатива и импульс к движению без доказательства чужого намерения.",
    },
    {
        "name": "Башня",
        "general": "Противоречие, нарушающее прямое развитие импульса.",
    },
    {
        "name": "Звезда",
        "general": "Надежда и открытая возможность, но не совершённое действие.",
    },
]

CHOICE_QUESTION = (
    "Мы тепло общаемся, но потом он надолго пропадает. "
    "Стоит ли продолжать этот контакт?"
)
CHOICE_CARDS = [
    {"name": "Солнце", "love": "Теплота и открытость моментов общения."},
    {"name": "Отшельник", "love": "Дистанция и паузы без объяснения чужих причин."},
    {
        "name": "Умеренность",
        "love": "Подходящая пользователю мера и формат связи.",
    },
]


def valid_analysis(
    route="initiative",
    cards=INITIATIVE_CARDS,
):
    if route == "initiative":
        return {
            "question_route": route,
            "direct_answer": (
                "Возможность первого шага остаётся открытой, но карты не дают "
                "уверенного указания, что инициатива обязательно проявится."
            ),
            "card_roles": [
                {
                    "card": "Колесница",
                    "contribution": "Поддерживает тему движения и первого шага.",
                },
                {
                    "card": "Башня",
                    "contribution": "Нарушает прямое развитие этого импульса.",
                },
                {
                    "card": "Звезда",
                    "contribution": "Сохраняет надежду, не подтверждая действие.",
                },
            ],
            "central_dynamic": (
                "Импульс к движению сталкивается с сильным противоречием, после "
                "которого возможность остаётся, но не становится фактом."
            ),
            "psychological_reflection": (
                "Постоянные мысли о человеке делают ожидание его шага заметной "
                "частью вопроса."
            ),
            "unknowns": [
                "Нельзя установить намерения человека и момент возможного контакта."
            ],
            "reality_anchor": "Самостоятельное содержательное сообщение или звонок.",
            "closing_question": (
                "Какое действие вы сами сочтёте настоящей инициативой?"
            ),
        }
    return {
        "question_route": route,
        "direct_answer": (
            "Продолжение может иметь ценность, если формат контакта соответствует "
            "потребности пользователя во взаимности и устойчивости."
        ),
        "card_roles": [
            {"card": "Солнце", "contribution": "Подчёркивает теплоту общения."},
            {"card": "Отшельник", "contribution": "Добавляет дистанцию и паузы."},
            {
                "card": "Умеренность",
                "contribution": "Связывает контраст через подходящую меру участия.",
            },
        ],
        "central_dynamic": (
            "Теплота контакта сосуществует с прерывистостью, поэтому качество "
            "эпизодов не равно устойчивости связи."
        ),
        "psychological_reflection": (
            "Выбор связан с тем, какой ритм и взаимность нужны пользователю."
        ),
        "unknowns": ["Нельзя установить причины чужих пауз."],
        "reality_anchor": "Взаимная инициатива и регулярность общения.",
        "closing_question": (
            "Какая взаимность нужна вам, чтобы продолжение ощущалось ценным?"
        ),
    }


VALID_INITIATIVE_TEXT = """Возможность первого шага здесь остаётся, но сочетание не даёт уверенного «да». Скорее карты показывают импульс, который сталкивается с сильным противоречием, поэтому контакт нельзя считать уже определившимся событием. Это не закрывает возможность общения, а лишь оставляет её пока без ясного подтверждения.

Колесница усиливает тему движения и инициативы, Башня резко нарушает прямое развитие этого порыва, а Звезда сохраняет надежду и открытую возможность. Вместе они говорят о разнице между желанием увидеть движение и самим действием: перспектива не закрыта, но пока не получила ясного подтверждения в реальности.

Вопрос также показывает, насколько много внимания занимает ожидание чужого шага. Реальным знаком инициативы будет самостоятельное и содержательное продолжение общения без предварительного действия с вашей стороны. Какое конкретное проявление вы сами сочтёте настоящим первым шагом?"""


VALID_CHOICE_TEXT = """Этот контакт может оставаться ценным, но ответ зависит не только от теплоты ваших разговоров. Важно и то, насколько прерывистый ритм общения соответствует вашей потребности во взаимности и устойчивости.

Солнце подчёркивает радость и открытость в моменты близости, Отшельник добавляет к ним дистанцию и долгие паузы, а Умеренность связывает эти разные стороны через поиск подходящей вам меры участия. Вместе карты показывают, что приятные эпизоды и надёжность связи — не одно и то же, хотя оба элемента могут быть значимы.

Расклад не выбирает вместо вас и не объясняет причины чужого молчания. Он предлагает сравнить, что этот контакт даёт вам и насколько взаимно поддерживается во времени. Какая частота общения и какая встречная инициатива необходимы вам, чтобы продолжение этой связи действительно ощущалось ценным?"""


class PromptTests(unittest.TestCase):
    def test_analysis_is_interpretive_not_code_router(self):
        self.assertIn("содержательный бриф", ANALYSIS_SYSTEM_V7)
        self.assertIn("central_dynamic", ANALYSIS_SYSTEM_V7)
        self.assertNotIn("interaction_code", ANALYSIS_SYSTEM_V7)
        self.assertNotIn("Не пишите толкование", ANALYSIS_SYSTEM_V7)

    def test_analysis_schema_contains_meaningful_fields(self):
        required = set(ANALYSIS_SCHEMA_V7["required"])
        self.assertIn("direct_answer", required)
        self.assertIn("card_roles", required)
        self.assertIn("psychological_reflection", required)
        self.assertIn("unknowns", required)

    def test_analysis_prompt_contains_question_cards_positions_and_meanings(self):
        prompt = build_analysis_prompt_v7(
            INITIATIVE_QUESTION,
            INITIATIVE_CARDS,
            "initiative",
        )
        self.assertIn(INITIATIVE_QUESTION, prompt)
        self.assertIn("Колесница", prompt)
        self.assertIn("Башня", prompt)
        self.assertIn("Звезда", prompt)
        self.assertIn("Инициатива", prompt)
        self.assertIn("central_dynamic", prompt)

    def test_editor_requests_natural_prose_and_probability_language(self):
        self.assertIn("скорее", EDITOR_SYSTEM_V7)
        self.assertIn("возможно", EDITOR_SYSTEM_V7)
        self.assertIn("живой собеседник", EDITOR_SYSTEM_V7)
        self.assertIn("Не прячь", EDITOR_SYSTEM_V7)

    def test_editor_prompt_contains_verified_brief(self):
        prompt = build_editor_prompt_v7(
            INITIATIVE_QUESTION,
            INITIATIVE_CARDS,
            "initiative",
            valid_analysis(),
        )
        self.assertIn("central_dynamic", prompt)
        self.assertIn("Колесница", prompt)
        self.assertIn("настоящей инициативой", prompt)
        self.assertIn("Эталон уровня теплоты", prompt)


class AnalysisValidationTests(unittest.TestCase):
    def test_valid_interpretive_brief_passes(self):
        self.assertEqual(
            validate_analysis_v7(
                valid_analysis(),
                cards=INITIATIVE_CARDS,
                route="initiative",
            ),
            [],
        )

    def test_all_cards_must_be_present_in_order(self):
        payload = valid_analysis()
        payload["card_roles"][1]["card"] = "Луна"
        issues = validate_analysis_v7(
            payload,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("analysis_card_order_or_names", issues)

    def test_missing_unknowns_is_rejected(self):
        payload = valid_analysis()
        payload["unknowns"] = []
        issues = validate_analysis_v7(
            payload,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("invalid:unknowns", issues)

    def test_mind_reading_in_brief_is_rejected(self):
        payload = valid_analysis()
        payload["central_dynamic"] = "Он боится написать первым."
        issues = validate_analysis_v7(
            payload,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("unsafe:mind_reading", issues)

    def test_certain_prediction_in_brief_is_rejected(self):
        payload = valid_analysis()
        payload["direct_answer"] = "Он точно напишет первым."
        issues = validate_analysis_v7(
            payload,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("unsafe:certain_future", issues)


class FinalValidationTests(unittest.TestCase):
    def test_natural_initiative_answer_passes(self):
        issues, warnings = validate_final_v7(
            {"final_text": VALID_INITIATIVE_TEXT},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])

    def test_natural_choice_answer_passes(self):
        issues, warnings = validate_final_v7(
            {"final_text": VALID_CHOICE_TEXT},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
        )
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])

    def test_style_problem_is_warning_not_hard_failure(self):
        text = VALID_INITIATIVE_TEXT.replace(
            "Реальным знаком инициативы",
            "Наблюдаемым критерием и достаточной опорой",
        )
        issues, warnings = validate_final_v7(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertEqual(issues, [])
        self.assertTrue(any("bureaucratic" in warning for warning in warnings))

    def test_unsupported_partner_role_is_warning(self):
        warnings = style_warnings_v7(
            VALID_INITIATIVE_TEXT.replace("чужого шага", "шага партнёра"),
            INITIATIVE_QUESTION,
        )
        self.assertIn("unsupported_role:partner", warnings)

    def test_missing_card_is_hard_failure(self):
        text = VALID_INITIATIVE_TEXT.replace("Звезда", "последняя карта")
        issues, _ = validate_final_v7(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertIn("final_missing_cards:Звезда", issues)

    def test_mind_reading_is_hard_failure(self):
        text = VALID_INITIATIVE_TEXT.replace(
            "Вопрос также показывает",
            "Он хочет написать первым. Вопрос также показывает",
        )
        issues, _ = validate_final_v7(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertIn("unsafe:mind_reading", issues)

    def test_certain_future_is_hard_failure(self):
        issues = hard_safety_issues_v7("Он обязательно выйдет на связь.")
        self.assertIn("unsafe:certain_future", issues)

    def test_probability_language_is_allowed(self):
        self.assertEqual(
            hard_safety_issues_v7("Возможно, он выйдет на связь, но карты этого не гарантируют."),
            [],
        )

    def test_cleaning_removes_only_markdown_stars(self):
        source = "**Колесница** сохраняет содержание, а *Звезда* — знак надежды."
        self.assertEqual(
            clean_stars_v7(source),
            "Колесница сохраняет содержание, а Звезда — знак надежды.",
        )


class OrchestrationTests(unittest.TestCase):
    def test_success_uses_exactly_two_calls(self):
        calls = []

        def analyst(prompt):
            calls.append("analysis")
            return json.dumps(valid_analysis(), ensure_ascii=False)

        def editor(prompt):
            calls.append("editor")
            return json.dumps({"final_text": VALID_INITIATIVE_TEXT}, ensure_ascii=False)

        result = generate_reading_v7(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            analysis_call=analyst,
            editor_call=editor,
        )
        self.assertEqual(calls, ["analysis", "editor"])
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["stage"], "complete")

    def test_style_warning_does_not_trigger_fallback(self):
        warned_text = VALID_INITIATIVE_TEXT.replace(
            "Реальным знаком инициативы",
            "Наблюдаемым критерием инициативы",
        )
        result = generate_reading_v7(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            analysis_call=lambda _: json.dumps(valid_analysis(), ensure_ascii=False),
            editor_call=lambda _: json.dumps(
                {"final_text": warned_text}, ensure_ascii=False
            ),
        )
        self.assertFalse(result["used_fallback"])
        self.assertTrue(result["warnings"])
        self.assertEqual(result["issues"], [])

    def test_invalid_analysis_stops_before_editor(self):
        calls = []

        def analyst(prompt):
            calls.append("analysis")
            return "{"

        def editor(prompt):
            calls.append("editor")
            return json.dumps({"final_text": VALID_INITIATIVE_TEXT}, ensure_ascii=False)

        result = generate_reading_v7(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            analysis_call=analyst,
            editor_call=editor,
        )
        self.assertEqual(calls, ["analysis"])
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "analysis")

    def test_unsafe_editor_text_triggers_fallback(self):
        unsafe = VALID_INITIATIVE_TEXT.replace(
            "Вопрос также показывает",
            "Он думает о вас и точно напишет. Вопрос также показывает",
        )
        result = generate_reading_v7(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            analysis_call=lambda _: json.dumps(valid_analysis(), ensure_ascii=False),
            editor_call=lambda _: json.dumps({"final_text": unsafe}, ensure_ascii=False),
        )
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "editor")
        self.assertTrue(any(issue.startswith("unsafe:") for issue in result["issues"]))

    def test_personal_choice_route_uses_same_two_pass_flow(self):
        result = generate_reading_v7(
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
            topic="love",
            analysis_call=lambda _: json.dumps(
                valid_analysis("personal_choice", CHOICE_CARDS), ensure_ascii=False
            ),
            editor_call=lambda _: json.dumps(
                {"final_text": VALID_CHOICE_TEXT}, ensure_ascii=False
            ),
        )
        self.assertEqual(result["route"], "personal_choice")
        self.assertFalse(result["used_fallback"])


if __name__ == "__main__":
    unittest.main()
