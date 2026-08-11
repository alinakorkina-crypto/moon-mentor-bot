import json
import unittest

from reading_engine_v5 import (
    ANALYSIS_SCHEMA_V5,
    EDITOR_SCHEMA_V5,
    PERSONAL_POSITIONS_V5,
    build_analysis_prompt_v5,
    build_editor_prompt_v5,
    clean_markdown_stars_v5,
    generate_personal_reading_v5,
    validate_analysis_v5,
    validate_final_text_v5,
)
QUESTION = "Выйдет тот, о ком я думаю постоянно, первым на контакт?"
CARDS = [
    {
        "name": "Колесница",
        "general": (
            "Импульс к движению и проявлению, который сам по себе ещё не доказывает "
            "конкретное действие другого человека."
        ),
    },
    {
        "name": "Башня",
        "general": (
            "Резкое нарушение прежнего сценария, препятствие или перелом, который "
            "меняет направление исходного импульса."
        ),
    },
    {
        "name": "Звезда",
        "general": (
            "Открытая возможность, дистанционная надежда и перспектива без гарантии "
            "близкого практического шага."
        ),
    },
]


def valid_analysis():
    return {
        "question_mode": "initiative",
        "facts_used": ["думаю постоянно", "первым на контакт"],
        "unknowns_kept_open": [
            "намерение другого человека",
            "будущее действие",
            "срок возможного контакта",
        ],
        "card_roles": [
            {
                "card": card["name"],
                "position": PERSONAL_POSITIONS_V5[index],
                "contribution": contribution,
            }
            for index, (card, contribution) in enumerate(
                zip(
                    CARDS,
                    (
                        "создаёт импульс движения",
                        "нарушает и перенаправляет импульс",
                        "оставляет возможность открытой без гарантии шага",
                    ),
                )
            )
        ],
        "answer_tendency": "mixed",
        "direct_answer_basis": (
            "Импульс присутствует, но проходит через резкий перелом и не становится "
            "достоверным указанием на действие."
        ),
        "combination_synthesis": (
            "Колесница создаёт движение, Башня нарушает его прямую линию, а Звезда "
            "оставляет надежду и возможность открытыми без подтверждённого шага."
        ),
        "observable_criterion": "самостоятельная инициатива в реальном общении",
        "reflection_question": (
            "Сколько времени пользователь готов оставлять возможность открытой без действий?"
        ),
    }


def valid_final():
    return {
        "final_text": (
            "По символике сочетания здесь нет уверенного указания на скорый первый шаг. "
            "Движение возможно, но оно проходит через сильное препятствие, поэтому расклад "
            "скорее оставляет вопрос открытым, чем обещает конкретный контакт. Само ожидание "
            "здесь ещё не равно сформированной готовности проявиться.\n\n"
            "Колесница создаёт импульс к проявлению, но Башня резко нарушает его направление. "
            "Звезда после этого сохраняет надежду и возможность продолжения, однако переводит "
            "их в более отдалённую перспективу. Вместе карты показывают движение, которое "
            "не исчезло полностью, но пока не сложилось в ясный самостоятельный шаг.\n\n"
            "Проверяемым признаком станет инициатива, возникшая без вашего напоминания или "
            "толчка, а не само ощущение возможного возвращения. Сколько времени вы готовы "
            "оставлять эту возможность открытой без конкретного контакта?"
        )
    }


class ReadingEngineV5Tests(unittest.TestCase):
    def test_schemas_require_structured_analysis_and_final_text(self):
        self.assertIn("combination_synthesis", ANALYSIS_SCHEMA_V5["required"])
        self.assertEqual(EDITOR_SCHEMA_V5["required"], ["final_text"])

    def test_analysis_prompt_contains_question_positions_and_cards(self):
        prompt = build_analysis_prompt_v5(QUESTION, CARDS)
        self.assertIn(QUESTION, prompt)
        for index, card in enumerate(CARDS):
            self.assertIn(card["name"], prompt)
            self.assertIn(PERSONAL_POSITIONS_V5[index], prompt)

    def test_editor_prompt_contains_verified_analysis(self):
        prompt = build_editor_prompt_v5(QUESTION, CARDS, valid_analysis())
        self.assertIn(QUESTION, prompt)
        self.assertIn("combination_synthesis", prompt)
        self.assertIn("Колесница", prompt)

    def test_valid_analysis_passes(self):
        self.assertEqual(
            validate_analysis_v5(
                valid_analysis(), user_question=QUESTION, cards=CARDS
            ),
            [],
        )

    def test_analysis_rejects_unsupported_fact(self):
        payload = valid_analysis()
        payload["facts_used"].append("он уже обещал написать")
        self.assertIn(
            "unsupported_fact",
            validate_analysis_v5(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_analysis_requires_every_card(self):
        payload = valid_analysis()
        payload["card_roles"].pop()
        self.assertIn(
            "card_roles_mismatch",
            validate_analysis_v5(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_analysis_requires_card_positions_in_order(self):
        payload = valid_analysis()
        payload["card_roles"][0]["position"] = "Другая позиция"
        self.assertIn(
            "card_positions_mismatch",
            validate_analysis_v5(payload, user_question=QUESTION, cards=CARDS),
        )

    def test_analysis_synthesis_must_include_all_cards(self):
        payload = valid_analysis()
        payload["combination_synthesis"] = "Колесница сталкивается с Башней."
        issues = validate_analysis_v5(payload, user_question=QUESTION, cards=CARDS)
        self.assertIn("analysis_missing_cards:Звезда", issues)

    def test_valid_final_text_passes(self):
        self.assertEqual(validate_final_text_v5(valid_final(), cards=CARDS), [])

    def test_final_text_rejects_categorical_prediction(self):
        payload = valid_final()
        payload["final_text"] = payload["final_text"].replace(
            "По символике сочетания", "Он точно выйдет на контакт. По символике сочетания"
        )
        self.assertIn("high_risk_claim", validate_final_text_v5(payload, cards=CARDS))

    def test_final_text_requires_three_paragraphs(self):
        payload = valid_final()
        payload["final_text"] = payload["final_text"].replace("\n\n", " ")
        self.assertIn("paragraph_count", validate_final_text_v5(payload, cards=CARDS))

    def test_final_text_accepts_declined_card_names(self):
        payload = valid_final()
        payload["final_text"] = (
            payload["final_text"]
            .replace("Колесница", "Колесницы")
            .replace("Башня", "Башни")
            .replace("Звезда", "Звезды")
        )
        self.assertNotIn(
            "final_missing_cards",
            " ".join(validate_final_text_v5(payload, cards=CARDS)),
        )

    def test_cleaning_only_removes_markdown_stars(self):
        self.assertEqual(
            clean_markdown_stars_v5("**Колесница** и *Башня*."),
            "Колесница и Башня.",
        )

    def test_success_uses_exactly_two_calls(self):
        calls = []
        result = generate_personal_reading_v5(
            user_question=QUESTION,
            cards=CARDS,
            analysis_call=lambda prompt: calls.append("analysis") or json.dumps(
                valid_analysis(), ensure_ascii=False
            ),
            editor_call=lambda prompt: calls.append("editor") or json.dumps(
                valid_final(), ensure_ascii=False
            ),
        )
        self.assertEqual(calls, ["analysis", "editor"])
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["ai_requests"], 2)

    def test_invalid_analysis_stops_before_editor(self):
        calls = []
        result = generate_personal_reading_v5(
            user_question=QUESTION,
            cards=CARDS,
            analysis_call=lambda prompt: calls.append("analysis") or "{}",
            editor_call=lambda prompt: calls.append("editor") or "{}",
        )
        self.assertEqual(calls, ["analysis"])
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "analysis")

    def test_invalid_editor_uses_fallback_after_two_calls(self):
        calls = []
        result = generate_personal_reading_v5(
            user_question=QUESTION,
            cards=CARDS,
            analysis_call=lambda prompt: calls.append("analysis") or json.dumps(
                valid_analysis(), ensure_ascii=False
            ),
            editor_call=lambda prompt: calls.append("editor") or "{}",
        )
        self.assertEqual(calls, ["analysis", "editor"])
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "editor")


if __name__ == "__main__":
    unittest.main()
