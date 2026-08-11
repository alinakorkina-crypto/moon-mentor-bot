import json
from pathlib import Path
import unittest

from reading_engine_v6 import (
    ANALYSIS_SCHEMA_V6,
    ANALYSIS_SYSTEM_V6,
    EDITOR_SCHEMA_V6,
    EDITOR_SYSTEM_V6,
    ROUTE_CONFIG_V6,
    build_analysis_prompt_v6,
    build_editor_prompt_v6,
    clean_stars_v6,
    count_words_v6,
    fallback_v6,
    generate_reading_v6,
    infer_question_route_v6,
    missing_cards_v6,
    normalize_final_layout_v6,
    parse_json_v6,
    prepare_cards_v6,
    validate_analysis_v6,
    validate_final_v6,
)


INITIATIVE_QUESTION = "Выйдет тот, о ком я думаю постоянно, первым на контакт?"
INITIATIVE_CARDS = [
    {
        "name": "Колесница",
        "general": (
            "Импульс к движению и выбранное направление; это символическая тема, "
            "а не доказательство намерения другого человека."
        ),
    },
    {
        "name": "Башня",
        "general": (
            "Резкое противоречие и утрата прежней опоры; не подтверждает, что "
            "конкретное событие уже произошло или произойдёт."
        ),
    },
    {
        "name": "Звезда",
        "general": (
            "Открытая возможность и надежда на расстоянии; важно отличать перспективу "
            "от совершённого шага."
        ),
    },
]

CHOICE_QUESTION = (
    "Мы тепло общаемся, но потом он надолго пропадает. "
    "Стоит ли продолжать этот контакт?"
)
CHOICE_CARDS = [
    {"name": "Солнце", "general": "Тепло и открытость в описанных эпизодах общения."},
    {
        "name": "Отшельник",
        "general": "Дистанция и пауза как наблюдаемая часть контакта, без объяснения причин.",
    },
    {
        "name": "Умеренность",
        "general": "Подходящая человеку мера и формат участия, а не совет терпеть всё.",
    },
]


def initiative_analysis():
    return {
        "question_route": "initiative",
        "question_quotes": ["думаю постоянно", "первым на контакт"],
        "interaction_code": "restriction",
        "focus_code": "evidence_threshold",
        "tendency_code": "contradictory",
        "criterion_code": "independent_contact",
    }


def choice_analysis():
    return {
        "question_route": "personal_choice",
        "question_quotes": ["тепло общаемся", "надолго пропадает"],
        "interaction_code": "contrast",
        "focus_code": "reciprocity",
        "tendency_code": "conditional",
        "criterion_code": "mutual_initiative",
    }


INITIATIVE_FINAL = (
    "По символике этого расклада картина смешанная: возможность первого шага есть, "
    "но карты не дают уверенного подтверждения самостоятельной инициативы. Здесь "
    "заметны одновременно импульс к контакту и сильное противоречие, поэтому вопрос "
    "пока разумнее оставить открытым.\n\n"
    "Колесница поддерживает тему движения, однако Башня нарушает её устойчивость и "
    "не позволяет принять сам импульс за уже складывающееся действие. Звезда смягчает "
    "этот разрыв и сохраняет перспективу, но говорит скорее о возможности и надежде, "
    "чем о подтверждённом шаге. Вместе карты не описывают хронологию событий, а "
    "показывают напряжение между движением, сбоем и открытым продолжением.\n\n"
    "Наблюдаемым признаком станет содержательное сообщение или самостоятельное "
    "продолжение разговора без вашего предварительного шага. Какое конкретное "
    "проявление вы сами сочтёте настоящей инициативой?"
)


CHOICE_FINAL = (
    "По символике расклада решение зависит от того, подходит ли вам контакт, где "
    "тёплые периоды сменяются долгими паузами. Карты не выбирают вместо вас, но "
    "помогают сравнить ценность общения с ценой его прерывистого ритма.\n\n"
    "Солнце подчёркивает живое тепло в те моменты, когда связь есть, а Отшельник "
    "добавляет к этой картине дистанцию, уже названную в вопросе. Умеренность не "
    "обещает изменить другого человека и не призывает терпеть неопределённость; она "
    "связывает обе карты через поиск подходящей именно вам меры участия. Общий рисунок "
    "здесь не о причинах исчезновений, а о совместимости такого формата с вашими "
    "потребностями.\n\n"
    "Проверяемым ориентиром может стать взаимность инициативы после очередной паузы и "
    "ваше состояние между разговорами. Какой ритм общения оставляет вам достаточно "
    "спокойствия и ощущения взаимности?"
)


class RoutingTests(unittest.TestCase):
    def test_initiative_route_has_priority_over_choice_wording(self):
        self.assertEqual(
            infer_question_route_v6("Стоит ли ждать, что он выйдет на контакт?"),
            "initiative",
        )

    def test_common_initiative_phrasings(self):
        for question in (
            "Она напишет мне сама?",
            "Проявится ли этот человек?",
            "Сделает ли он первый шаг?",
        ):
            with self.subTest(question=question):
                self.assertEqual(infer_question_route_v6(question), "initiative")

    def test_personal_choice_route(self):
        self.assertEqual(infer_question_route_v6(CHOICE_QUESTION), "personal_choice")

    def test_unsupported_route(self):
        self.assertEqual(infer_question_route_v6("Что происходит в моей жизни?"), "unsupported")


class PromptTests(unittest.TestCase):
    def test_schemas_require_complete_payloads(self):
        self.assertIn("question_quotes", ANALYSIS_SCHEMA_V6["required"])
        self.assertIn("interaction_code", ANALYSIS_SCHEMA_V6["required"])
        self.assertIn("focus_code", ANALYSIS_SCHEMA_V6["required"])
        self.assertIn("tendency_code", ANALYSIS_SCHEMA_V6["required"])
        self.assertIn("criterion_code", ANALYSIS_SCHEMA_V6["required"])
        self.assertNotIn("central_pattern", ANALYSIS_SCHEMA_V6["required"])
        self.assertNotIn("card_roles", ANALYSIS_SCHEMA_V6["required"])
        self.assertEqual(EDITOR_SCHEMA_V6["required"], ["final_text"])

    def test_analysis_prompt_contains_route_positions_and_no_timeline_rule(self):
        prompt = build_analysis_prompt_v6(
            INITIATIVE_QUESTION, INITIATIVE_CARDS, "initiative"
        )
        for position in ROUTE_CONFIG_V6["initiative"]["positions"]:
            self.assertIn(position, prompt)
        self.assertIn("не является временной последовательностью", prompt)
        self.assertIn("contradictory", prompt)
        self.assertIn("evidence_threshold", prompt)

    def test_editor_prompt_contains_verified_analysis_and_style_example(self):
        prompt = build_editor_prompt_v6(
            INITIATIVE_QUESTION,
            INITIATIVE_CARDS,
            "initiative",
            initiative_analysis(),
        )
        self.assertIn("Проверенный план", prompt)
        self.assertIn("Эталон тона", prompt)
        self.assertIn("Колесница", prompt)
        self.assertIn("evidence_threshold", prompt)
        self.assertIn("independent_contact", prompt)
        for prepared_card in prepare_cards_v6(INITIATIVE_CARDS, "initiative"):
            self.assertIn(prepared_card["position"], prompt)
            self.assertIn(prepared_card["meaning"], prompt)
        self.assertIn(
            "одна тема заметно ограничивает или ослабляет другую",
            prompt,
        )
        self.assertIn(
            "самостоятельное сообщение или звонок без предварительного шага пользователя",
            prompt,
        )

    def test_system_prompts_split_analysis_from_prose(self):
        self.assertIn("Не пишите толкование", ANALYSIS_SYSTEM_V6)
        self.assertIn("ровно 3 коротких абзаца", EDITOR_SYSTEM_V6)

    def test_card_positions_are_route_specific(self):
        initiative = prepare_cards_v6(INITIATIVE_CARDS, "initiative")
        choice = prepare_cards_v6(CHOICE_CARDS, "personal_choice")
        self.assertNotEqual(initiative[0]["position"], choice[0]["position"])


class JsonTransportTests(unittest.TestCase):
    def test_parser_accepts_nbsp_and_fence(self):
        payload, issues = parse_json_v6('```json\n{\n\u00a0"ok": true\n}\n```')
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(issues, [])

    def test_parser_labels_truncated_json(self):
        payload, issues = parse_json_v6('{"answer": "not finished')
        self.assertIsNone(payload)
        self.assertEqual(issues, ["truncated_json"])


class AiReaderConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).with_name("ai_reader_v6.py").read_text(
            encoding="utf-8"
        )

    def test_both_passes_use_low_thinking_and_4096_output_limit(self):
        self.assertEqual(
            self.source.count('ThinkingConfig(thinking_level="low")'),
            2,
        )
        self.assertEqual(self.source.count("max_output_tokens=4096"), 2)

    def test_gemini_3_config_omits_legacy_sampling_controls(self):
        for setting in ("temperature=", "top_p=", "candidate_count=", "seed="):
            with self.subTest(setting=setting):
                self.assertNotIn(setting, self.source)


class AnalysisValidationTests(unittest.TestCase):
    def test_valid_initiative_analysis(self):
        self.assertEqual(
            validate_analysis_v6(
                initiative_analysis(),
                question=INITIATIVE_QUESTION,
                cards=INITIATIVE_CARDS,
                route="initiative",
            ),
            [],
        )

    def test_valid_choice_analysis(self):
        self.assertEqual(
            validate_analysis_v6(
                choice_analysis(),
                question=CHOICE_QUESTION,
                cards=CHOICE_CARDS,
                route="personal_choice",
            ),
            [],
        )

    def test_rejects_unsupported_question_quote(self):
        payload = initiative_analysis()
        payload["question_quotes"] = ["между ними произошла ссора"]
        issues = validate_analysis_v6(
            payload,
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("unsupported_question_quote", issues)

    def test_rejects_wrong_tendency(self):
        payload = initiative_analysis()
        payload["tendency_code"] = "definitely_yes"
        issues = validate_analysis_v6(
            payload,
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("invalid_tendency", issues)

    def test_rejects_unexpected_free_text_field(self):
        payload = initiative_analysis()
        payload["central_pattern"] = "Внутренний конфликт и идеализация."
        issues = validate_analysis_v6(
            payload,
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("unexpected_analysis_fields:central_pattern", issues)

    def test_rejects_unknown_focus_code(self):
        payload = initiative_analysis()
        payload["focus_code"] = "attachment_diagnosis"
        issues = validate_analysis_v6(
            payload,
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("invalid_focus_code", issues)

    def test_rejects_quote_without_real_source(self):
        payload = initiative_analysis()
        payload["question_quotes"] = ["между ними пауза"]
        issues = validate_analysis_v6(
            payload,
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("unsupported_question_quote", issues)

    def test_rejects_invalid_interaction_and_criterion_codes(self):
        payload = initiative_analysis()
        payload["interaction_code"] = "inner_conflict"
        payload["criterion_code"] = "wait_for_a_sign"
        issues = validate_analysis_v6(
            payload,
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("invalid_interaction_code", issues)
        self.assertIn("invalid_criterion_code", issues)

    def test_rejects_criterion_from_another_route(self):
        payload = initiative_analysis()
        payload["criterion_code"] = "mutual_initiative"
        issues = validate_analysis_v6(
            payload,
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("invalid_criterion_code", issues)


class FinalValidationTests(unittest.TestCase):
    def test_valid_initiative_final(self):
        self.assertEqual(
            validate_final_v6(
                {"final_text": INITIATIVE_FINAL},
                question=INITIATIVE_QUESTION,
                cards=INITIATIVE_CARDS,
            ),
            [],
        )

    def test_valid_choice_final(self):
        self.assertEqual(
            validate_final_v6(
                {"final_text": CHOICE_FINAL},
                question=CHOICE_QUESTION,
                cards=CHOICE_CARDS,
            ),
            [],
        )

    def test_rejects_future_claim(self):
        text = INITIATIVE_FINAL.replace(
            "картина смешанная", "картина смешанная, но он скоро выйдет"
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertIn("high_risk_claim", issues)

    def test_rejects_invented_story_detail(self):
        text = INITIATIVE_FINAL.replace(
            "пока разумнее оставить открытым",
            "в ближайшее время разумнее оставить открытым",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertIn("unsupported_story", issues)

    def test_rejects_pseudo_psychological_diagnosis(self):
        text = CHOICE_FINAL.replace(
            "Карты не выбирают вместо вас",
            "У вас тревожная привязанность. Карты не выбирают вместо вас",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
        )
        self.assertIn("pseudo_psychology", issues)

    def test_normalizes_blank_lines_with_spaces(self):
        source = INITIATIVE_FINAL.replace("\n\n", "\n   \n")
        normalized = normalize_final_layout_v6(source)
        self.assertEqual(normalized, INITIATIVE_FINAL)
        self.assertEqual(
            validate_final_v6(
                {"final_text": source},
                question=INITIATIVE_QUESTION,
                cards=INITIATIVE_CARDS,
            ),
            [],
        )

    def test_normalizes_three_single_line_paragraphs(self):
        source = INITIATIVE_FINAL.replace("\n\n", "\n")
        self.assertEqual(normalize_final_layout_v6(source), INITIATIVE_FINAL)

    def test_decodes_literal_json_newlines(self):
        source = INITIATIVE_FINAL.replace("\n\n", "\\n\\n")
        self.assertEqual(normalize_final_layout_v6(source), INITIATIVE_FINAL)

    def test_card_search_accepts_latin_lookalike(self):
        text = INITIATIVE_FINAL.replace("Колесница", "Kолесница")
        self.assertEqual(missing_cards_v6(text, INITIATIVE_CARDS), [])

    def test_card_search_accepts_instrumental_form(self):
        text = INITIATIVE_FINAL.replace(
            "Колесница поддерживает тему движения",
            "Колесницей поддерживается тема движения",
        )
        self.assertEqual(missing_cards_v6(text, INITIATIVE_CARDS), [])

    def test_rejects_inevitable_relationship_prediction(self):
        text = CHOICE_FINAL.replace(
            "Отшельник добавляет к этой картине дистанцию",
            "Отшельник добавляет неизбежную дистанцию",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
        )
        self.assertIn("unsupported_story", issues)

    def test_rejects_adaptation_as_condition(self):
        text = CHOICE_FINAL.replace(
            "решение зависит от того, подходит ли вам контакт",
            "решение зависит от того, готовы ли вы принять такой контакт",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
        )
        self.assertIn("adaptation_or_user_blame", issues)

    def test_relationship_requires_external_reality_criterion(self):
        text = CHOICE_FINAL.replace(
            "Проверяемым ориентиром может стать взаимность инициативы после очередной паузы и "
            "ваше состояние между разговорами. Какой ритм общения оставляет вам достаточно "
            "спокойствия и ощущения взаимности?",
            "Проверяемым ориентиром может стать ваше внутреннее спокойствие между разговорами. "
            "Что помогает вам сохранять эмоциональное равновесие?",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
        )
        self.assertIn("missing_relationship_reality_criterion", issues)

    def test_reflection_question_cannot_fake_relationship_criterion(self):
        text = CHOICE_FINAL.replace(
            "Проверяемым ориентиром может стать взаимность инициативы после очередной паузы и "
            "ваше состояние между разговорами. Какой ритм общения оставляет вам достаточно "
            "спокойствия и ощущения взаимности?",
            "Проверяемым ориентиром может стать только ваше внутреннее спокойствие. "
            "Как вы определите взаимность в этом общении?",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
        )
        self.assertIn("missing_relationship_reality_criterion", issues)

    def test_initiative_requires_external_reality_criterion(self):
        text = INITIATIVE_FINAL.replace(
            "Наблюдаемым признаком станет содержательное сообщение или самостоятельное "
            "продолжение разговора без вашего предварительного шага. Какое конкретное "
            "проявление вы сами сочтёте настоящей инициативой?",
            "Ориентиром станет ваше внутреннее спокойствие. Какое сообщение вы сочтёте "
            "настоящей инициативой?",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertIn("missing_initiative_reality_criterion", issues)

    def test_rejects_unsupported_psychological_inference(self):
        text = INITIATIVE_FINAL.replace(
            "Здесь заметны одновременно импульс к контакту",
            "Здесь заметен идеализированный образ и импульс к контакту",
        )
        issues = validate_final_v6(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
        )
        self.assertTrue(
            any(issue.startswith("unsupported_inference:") for issue in issues)
        )

    def test_rejects_inflected_unsupported_inferences(self):
        phrases = (
            "внутренними барьерами",
            "долгосрочной перспективой",
            "разрушительным влиянием",
            "редкими моментами",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                text = INITIATIVE_FINAL.replace(
                    "сильное противоречие",
                    f"сильное противоречие с {phrase}",
                )
                issues = validate_final_v6(
                    {"final_text": text},
                    question=INITIATIVE_QUESTION,
                    cards=INITIATIVE_CARDS,
                )
                self.assertTrue(
                    any(issue.startswith("unsupported_inference:") for issue in issues)
                )

    def test_fallbacks_meet_production_length(self):
        initiative = fallback_v6(INITIATIVE_QUESTION, INITIATIVE_CARDS, "initiative")
        choice = fallback_v6(CHOICE_QUESTION, CHOICE_CARDS, "personal_choice")
        for text in (initiative, choice):
            with self.subTest(text=text[:30]):
                self.assertGreaterEqual(count_words_v6(text), 100)
                self.assertLessEqual(count_words_v6(text), 170)

    def test_cleaning_removes_only_markdown_stars(self):
        source = "**Тёплый** контакт и *ясный* вопрос: 2 * 3."
        self.assertEqual(clean_stars_v6(source), "Тёплый контакт и ясный вопрос: 2 * 3.")


class PipelineTests(unittest.TestCase):
    def test_success_uses_exactly_two_calls(self):
        calls = []

        def analysis_call(prompt):
            calls.append(("analysis", prompt))
            return json.dumps(initiative_analysis(), ensure_ascii=False)

        def editor_call(prompt):
            calls.append(("editor", prompt))
            return json.dumps({"final_text": INITIATIVE_FINAL}, ensure_ascii=False)

        result = generate_reading_v6(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            analysis_call=analysis_call,
            editor_call=editor_call,
        )
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["ai_requests"], 2)
        self.assertEqual([kind for kind, _ in calls], ["analysis", "editor"])

    def test_invalid_analysis_does_not_call_editor(self):
        editor_calls = []

        result = generate_reading_v6(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            analysis_call=lambda _: "not json",
            editor_call=lambda prompt: editor_calls.append(prompt),
        )
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "analysis")
        self.assertEqual(result["ai_requests"], 1)
        self.assertEqual(editor_calls, [])

    def test_editor_formatting_is_repaired_without_fallback(self):
        result = generate_reading_v6(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            analysis_call=lambda _: json.dumps(
                initiative_analysis(), ensure_ascii=False
            ),
            editor_call=lambda _: json.dumps(
                {"final_text": INITIATIVE_FINAL.replace("\n\n", "\n   \n")},
                ensure_ascii=False,
            ),
        )
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["text"], INITIATIVE_FINAL)

    def test_rejected_editor_text_is_returned_for_diagnostics(self):
        unsafe_text = CHOICE_FINAL.replace(
            "решение зависит от того, подходит ли вам контакт",
            "решение зависит от того, готовы ли вы принять такой контакт",
        )
        result = generate_reading_v6(
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
            analysis_call=lambda _: json.dumps(choice_analysis(), ensure_ascii=False),
            editor_call=lambda _: json.dumps(
                {"final_text": unsafe_text}, ensure_ascii=False
            ),
        )
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "editor")
        self.assertIn("adaptation_or_user_blame", result["issues"])
        self.assertEqual(result["rejected_text"], unsafe_text)

    def test_unsupported_route_uses_no_ai(self):
        calls = []
        result = generate_reading_v6(
            question="Что происходит в моей жизни?",
            cards=INITIATIVE_CARDS,
            analysis_call=lambda prompt: calls.append(prompt),
            editor_call=lambda prompt: calls.append(prompt),
        )
        self.assertEqual(result["ai_requests"], 0)
        self.assertEqual(result["stage"], "routing")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
