import unittest

from reading_engine_v3 import (
    SPREAD_INSTRUCTIONS,
    SPREAD_POSITIONS,
    build_reading_v3_prompt,
    clean_reading_v3_answer,
    generate_reading_v3,
    inspect_reading_v3_answer,
    prepare_cards_v3,
)


SAMPLE_CARDS = [
    {
        "name": "Солнце",
        "general": "Тепло и ясность.",
        "love": "Тепло и открытость контакта.",
        "career": "Ясность и признание в работе.",
    },
    {
        "name": "Луна",
        "general": "Неясность и смешанные сигналы.",
        "love": "Неясность в динамике контакта.",
        "career": "Неполная информация об условиях.",
    },
    {
        "name": "Справедливость",
        "general": "Баланс и проверяемые условия.",
        "love": "Баланс участия и договорённости.",
        "career": "Условия, ответственность и договорённости.",
    },
    {
        "name": "Звезда",
        "general": "Ориентир, надежда и перспектива.",
        "love": "Мягкий символический ориентир.",
        "career": "Долгосрочный ориентир.",
    },
]


class ReadingEngineV3Tests(unittest.TestCase):
    def test_prompt_contains_exact_question_and_all_cards(self):
        question = "Стоит ли продолжать этот контакт?"
        prompt = build_reading_v3_prompt(
            "love", question, SAMPLE_CARDS[:3], "love"
        )
        self.assertIn(question, prompt)
        for card in SAMPLE_CARDS[:3]:
            self.assertIn(card["name"], prompt)

    def test_prompt_requires_180_to_220_words(self):
        prompt = build_reading_v3_prompt(
            "career",
            "Соглашаться ли на новую работу?",
            SAMPLE_CARDS[:3],
            "career",
        )
        self.assertIn("строго 180–220 слов", prompt)

    def test_prompt_requires_four_natural_paragraphs(self):
        prompt = build_reading_v3_prompt(
            "love", "Продолжать общение?", SAMPLE_CARDS[:3], "love"
        )
        self.assertIn("Напишите четыре коротких абзаца", prompt)
        self.assertIn("Естественность и точность важнее", prompt)
        self.assertNotIn("ровно 13 предложений", prompt)

    def test_prompt_requires_direct_answer_and_central_theme(self):
        prompt = build_reading_v3_prompt(
            "love", "Продолжать общение?", SAMPLE_CARDS[:3], "love"
        )
        self.assertIn("Начни с прямого ответа", prompt)
        self.assertIn("одну центральную тему", prompt)
        self.assertIn("главное противоречие или усиление", prompt)

    def test_prompt_requires_observable_criterion_next_step_and_question(self):
        prompt = build_reading_v3_prompt(
            "career", "Принимать предложение?", SAMPLE_CARDS[:3], "career"
        )
        self.assertIn("один наблюдаемый критерий", prompt)
        self.assertIn("одним конкретным следующим шагом", prompt)
        self.assertIn("одним точным вопросом для размышления", prompt)

    def test_prompt_forbids_separate_card_retellings(self):
        prompt = build_reading_v3_prompt(
            "love", "Что важно увидеть?", SAMPLE_CARDS[:3], "love"
        )
        self.assertIn(
            "Не создавай отдельное толкование для каждой карты",
            prompt,
        )
        self.assertIn("Свяжи карты в одну линию", prompt)

    def test_love_instruction_forbids_waiting_and_adapting(self):
        instruction = SPREAD_INSTRUCTIONS["love"]
        self.assertIn("Не советуйте ждать", instruction)
        self.assertIn("терпеть исчезновения", instruction)
        self.assertIn("принимать человека «таким, какой он есть»", instruction)
        self.assertIn("подстраиваться", instruction)
        self.assertIn("поддерживают ли контакт двое", instruction)
        self.assertIn("не делайте вывод об", instruction)
        self.assertIn("отсутствии взаимности", instruction)
        self.assertIn("предложите пользователю проверить это как критерий", instruction)

    def test_love_instruction_forbids_accepting_current_dynamic(self):
        instruction = SPREAD_INSTRUCTIONS["love"]
        self.assertIn("принимать текущую динамику", instruction)
        self.assertIn("снижать ожидания", instruction)

    def test_prompt_forbids_mechanical_card_language(self):
        prompt = build_reading_v3_prompt(
            "love", "Продолжать общение?", SAMPLE_CARDS[:3], "love"
        )
        self.assertIn("карты показывают", prompt)
        self.assertIn("карта указывает", prompt)
        self.assertIn("карта подталкивает", prompt)
        self.assertIn("Не двигайтесь по картам по очереди", prompt)

    def test_prompt_forbids_strengthening_user_facts(self):
        prompt = build_reading_v3_prompt(
            "love", "Он иногда пропадает.", SAMPLE_CARDS[:3], "love"
        )
        self.assertIn("«пропадает» не превращай в «полный уход»", prompt)
        self.assertIn("«глубокую дистанцию»", prompt)
        self.assertIn("Не делай вывод об отсутствии взаимности", prompt)
        self.assertIn("Недостаток информации не называй скрытой", prompt)

    def test_prompt_forbids_invented_interactions(self):
        prompt = build_reading_v3_prompt(
            "love", "Продолжать общение?", SAMPLE_CARDS[:3], "love"
        )
        self.assertIn("Не придумывай встречу", prompt)
        self.assertIn("совместное занятие", prompt)
        self.assertIn("сообщение, разговор, эксперимент", prompt)
        self.assertIn("определить личную границу", prompt)

    def test_career_instruction_treats_unknowns_as_missing_information(self):
        instruction = SPREAD_INSTRUCTIONS["career"]
        self.assertIn("Недостаток информации", instruction)
        self.assertIn("не скрытой опасностью", instruction)
        self.assertIn("Не обещайте успех", instruction)
        self.assertIn("ключом к успеху", instruction)
        self.assertIn("после письменной конкретизации", instruction)
        self.assertIn("не соглашаться сначала", instruction)
        self.assertIn("Не предполагайте", instruction)

    def test_personal_question_does_not_invent_a_sphere(self):
        instruction = SPREAD_INSTRUCTIONS["personal_question"]
        self.assertIn("не придумывайте сферу", instruction)
        self.assertIn("какого контекста не хватает", instruction)

    def test_full_instruction_uses_four_position_sequence(self):
        instruction = SPREAD_INSTRUCTIONS["full"]
        self.assertIn("центральная тема", instruction)
        self.assertIn("осложнение", instruction)
        self.assertIn("опора", instruction)
        self.assertIn("направление внимания", instruction)

    def test_daily_card_has_short_structure_and_no_prediction(self):
        prompt = build_reading_v3_prompt(
            "daily_card", "Карта дня", SAMPLE_CARDS[:1], "general"
        )
        self.assertIn("90–130 слов", prompt)
        self.assertIn("Не предсказывайте событие дня", prompt)
        self.assertNotIn("ровно четыре коротких абзаца", prompt)

    def test_daily_and_full_positions_are_defined(self):
        daily = prepare_cards_v3(SAMPLE_CARDS[:1], "daily_card", "general")
        full = prepare_cards_v3(SAMPLE_CARDS, "full", "general")
        self.assertEqual(daily[0]["position"], "Фокус дня")
        self.assertEqual(
            [item["position"] for item in full],
            list(SPREAD_POSITIONS["full"]),
        )

    def test_prompt_marks_question_as_only_source_of_facts(self):
        question = "Он надолго пропадает. Продолжать контакт?"
        prompt = build_reading_v3_prompt(
            "love", question, SAMPLE_CARDS[:3], "love"
        )
        self.assertIn("Единственные допустимые факты о ситуации", prompt)
        self.assertIn(question, prompt)
        self.assertIn("Значения карт — символические ракурсы", prompt)

    def test_prompt_forbids_invented_reasons_for_distance(self):
        prompt = build_reading_v3_prompt(
            "love",
            "Он надолго пропадает. Продолжать контакт?",
            SAMPLE_CARDS[:3],
            "love",
        )
        self.assertIn("Не объясняй паузу или дистанцию", prompt)
        self.assertIn("внутренним ритмом", prompt)
        self.assertIn("характером", prompt)
        self.assertIn("склонности или готовность", prompt)

    def test_prompt_forbids_predictions_about_other_person(self):
        prompt = build_reading_v3_prompt(
            "love",
            "Он надолго пропадает. Продолжать контакт?",
            SAMPLE_CARDS[:3],
            "love",
        )
        self.assertIn("Не предсказывай, что человек вернётся", prompt)
        self.assertIn("предполагаемый будущий результат", prompt)

    def test_prompt_forbids_unsupported_certainty_phrases(self):
        prompt = build_reading_v3_prompt(
            "career", "Принимать предложение?", SAMPLE_CARDS[:3], "career"
        )
        self.assertIn("карта подтверждает", prompt)
        self.assertIn("это не отторжение", prompt)
        self.assertIn("скрытые детали", prompt)

    def test_topic_meanings_are_used(self):
        prepared = prepare_cards_v3(SAMPLE_CARDS[:3], "career", "career")
        self.assertEqual(prepared[0]["meaning"], SAMPLE_CARDS[0]["career"])
        self.assertEqual(prepared[1]["meaning"], SAMPLE_CARDS[1]["career"])

    def test_cleanup_removes_bold_and_italic_markers(self):
        answer = "Здесь **Солнце** поддерживает *ясный шаг*."
        self.assertEqual(
            clean_reading_v3_answer(answer),
            "Здесь Солнце поддерживает ясный шаг.",
        )

    def test_cleanup_preserves_text_and_whitespace(self):
        answer = "  Первый абзац.\n\n**Второй абзац.**  "
        self.assertEqual(
            clean_reading_v3_answer(answer),
            "  Первый абзац.\n\nВторой абзац.  ",
        )

    def test_cleanup_does_not_remove_unpaired_or_non_markdown_star(self):
        answer = "Цена * неизвестна; формула 2 * 3 остаётся без изменений."
        self.assertEqual(clean_reading_v3_answer(answer), answer)

    def test_diagnostics_report_valid_multi_card_format(self):
        answer = ("слово " * 45).strip()
        answer = "\n\n".join([answer] * 4)
        report = inspect_reading_v3_answer(answer, "love")
        self.assertEqual(report["word_count"], 180)
        self.assertEqual(report["paragraph_count"], 4)
        self.assertTrue(report["within_word_target"])
        self.assertTrue(report["has_expected_paragraphs"])
        self.assertEqual(report["issues"], [])

    def test_diagnostics_report_deviations_without_rewriting(self):
        answer = "Короткий ответ.\n\nВторой абзац."
        report = inspect_reading_v3_answer(answer, "career")
        self.assertEqual(answer, "Короткий ответ.\n\nВторой абзац.")
        self.assertIn("word_count:4", report["issues"])
        self.assertIn("paragraph_count:2", report["issues"])

    def test_daily_diagnostics_use_daily_targets(self):
        answer = ("фокус " * 30).strip()
        answer = "\n\n".join([answer] * 3)
        report = inspect_reading_v3_answer(answer, "daily_card")
        self.assertEqual(report["word_count"], 90)
        self.assertTrue(report["within_word_target"])
        self.assertTrue(report["has_expected_paragraphs"])

    def test_generation_makes_exactly_one_ai_call(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return "**Прямой ответ.** Следующий шаг."

        result = generate_reading_v3(
            spread_type="love",
            user_question="Продолжать контакт?",
            cards=SAMPLE_CARDS[:3],
            topic="love",
            ai_call=fake_ai,
        )

        self.assertEqual(len(calls), 1)
        self.assertIn("Продолжать контакт?", calls[0])
        self.assertEqual(result, "Прямой ответ. Следующий шаг.")

    def test_empty_ai_answer_returns_empty_string_without_retry(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return None

        result = generate_reading_v3(
            spread_type="career",
            user_question="Принимать предложение?",
            cards=SAMPLE_CARDS[:3],
            topic="career",
            ai_call=fake_ai,
        )

        self.assertEqual(result, "")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
