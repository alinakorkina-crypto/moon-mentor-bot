import unittest

from reading_engine_v3 import (
    SPREAD_INSTRUCTIONS,
    SPREAD_POSITIONS,
    SYSTEM_INSTRUCTION_V3,
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
    def test_prompt_contains_exact_question_and_cards(self):
        question = "Стоит ли продолжать этот контакт?"
        prompt = build_reading_v3_prompt("love", question, SAMPLE_CARDS[:3], "love")
        self.assertIn(question, prompt)
        for card in SAMPLE_CARDS[:3]:
            self.assertIn(card["name"], prompt)

    def test_prompt_requires_light_three_paragraph_format(self):
        prompt = build_reading_v3_prompt("love", "Продолжать?", SAMPLE_CARDS[:3], "love")
        self.assertIn("три лёгких абзаца", prompt)
        self.assertIn("110–145 слов", prompt)
        self.assertIn("Не повторяйте одну мысль", prompt)

    def test_system_instruction_keeps_decision_with_user(self):
        self.assertIn("Не принимайте решение за пользователя", SYSTEM_INSTRUCTION_V3)
        self.assertIn("не подталкивайте его к одному варианту", SYSTEM_INSTRUCTION_V3)
        self.assertIn("Окончательный выбор всегда остаётся", SYSTEM_INSTRUCTION_V3)

    def test_system_instruction_requires_direct_conditional_answer(self):
        self.assertIn("в первом предложении", SYSTEM_INSTRUCTION_V3)
        self.assertIn("ключевое условие выбора", SYSTEM_INSTRUCTION_V3)

    def test_system_instruction_requires_all_card_synthesis(self):
        self.assertIn("используйте все карты и позиции", SYSTEM_INSTRUCTION_V3)
        self.assertIn("но создавайте один", SYSTEM_INSTRUCTION_V3)
        self.assertIn("общий вывод", SYSTEM_INSTRUCTION_V3)
        self.assertIn("а не получать отдельный пересказ", SYSTEM_INSTRUCTION_V3)

    def test_system_instruction_does_not_impose_service_labels(self):
        for phrase in (
            "центральная дилемма",
            "наблюдаемый критерий",
            "условие решения",
            "практический ориентир",
        ):
            self.assertNotIn(phrase, SYSTEM_INSTRUCTION_V3)

    def test_system_instruction_starts_without_greeting(self):
        self.assertIn("без приветствия", SYSTEM_INSTRUCTION_V3)
        self.assertIn("Начинайте сразу с ответа", SYSTEM_INSTRUCTION_V3)

    def test_system_instruction_requests_natural_style(self):
        self.assertIn("легко, тепло и естественно", SYSTEM_INSTRUCTION_V3)
        self.assertIn("Избегайте канцелярита", SYSTEM_INSTRUCTION_V3)
        self.assertIn("эзотерического пафоса", SYSTEM_INSTRUCTION_V3)

    def test_love_instruction_leaves_mutuality_open(self):
        instruction = SPREAD_INSTRUCTIONS["love"]
        self.assertIn("разделите известное и неизвестное", instruction)
        self.assertIn("от какого наблюдаемого условия", instruction)
        self.assertIn("Используйте все три карты", instruction)
        self.assertIn("третья меняет общий вывод", instruction)

    def test_career_instruction_does_not_choose_or_promise(self):
        instruction = SPREAD_INSTRUCTIONS["career"]
        self.assertIn("Большая зарплата — названное преимущество", instruction)
        self.assertIn("недостаток информации", instruction)
        self.assertIn("Свяжите все карты в один вывод", instruction)
        self.assertIn("Не решайте за пользователя", instruction)

    def test_career_keeps_dedicated_stable_profile(self):
        prompt = build_reading_v3_prompt(
            "career", "Соглашаться?", SAMPLE_CARDS[:3], "career"
        )
        self.assertIn("выбор упирается в конкретный", prompt)
        self.assertIn("Соберите все карты в один вывод", prompt)
        self.assertIn("130–170 слов", prompt)

    def test_system_instruction_requires_formal_address(self):
        self.assertIn("Пишите на «вы»", SYSTEM_INSTRUCTION_V3)

    def test_system_instruction_forbids_mind_reading_and_predictions(self):
        self.assertIn("не как предсказание", SYSTEM_INSTRUCTION_V3)
        self.assertIn("Не объясняйте мотивы", SYSTEM_INSTRUCTION_V3)
        self.assertIn("мысли другого человека", SYSTEM_INSTRUCTION_V3)

    def test_system_instruction_marks_question_as_only_fact_source(self):
        self.assertIn("Фактами считайте только сведения", SYSTEM_INSTRUCTION_V3)
        self.assertIn("Значения карт", SYSTEM_INSTRUCTION_V3)
        self.assertIn("не подтверждают", SYSTEM_INSTRUCTION_V3)

    def test_personal_question_does_not_invent_sphere(self):
        instruction = SPREAD_INSTRUCTIONS["personal_question"]
        self.assertIn("не придумывайте сферу", instruction)

    def test_daily_and_full_positions_are_defined(self):
        daily = prepare_cards_v3(SAMPLE_CARDS[:1], "daily_card", "general")
        full = prepare_cards_v3(SAMPLE_CARDS, "full", "general")
        self.assertEqual(daily[0]["position"], "Фокус дня")
        self.assertEqual([item["position"] for item in full], list(SPREAD_POSITIONS["full"]))

    def test_topic_meanings_are_used(self):
        prepared = prepare_cards_v3(SAMPLE_CARDS[:3], "career", "career")
        self.assertEqual(prepared[0]["meaning"], SAMPLE_CARDS[0]["career"])
        self.assertEqual(prepared[1]["meaning"], SAMPLE_CARDS[1]["career"])

    def test_cleanup_removes_only_paired_emphasis(self):
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

    def test_cleanup_preserves_unpaired_or_non_markdown_star(self):
        answer = "Цена * неизвестна; формула 2 * 3 остаётся."
        self.assertEqual(clean_reading_v3_answer(answer), answer)

    def test_diagnostics_accept_valid_multi_card_format(self):
        paragraph = ("слово " * 45).strip()
        report = inspect_reading_v3_answer("\n\n".join([paragraph] * 3), "love")
        self.assertEqual(report["word_count"], 135)
        self.assertEqual(report["paragraph_count"], 3)
        self.assertTrue(report["within_word_target"])
        self.assertTrue(report["has_expected_paragraphs"])
        self.assertEqual(report["issues"], [])

    def test_diagnostics_report_deviations_without_rewriting(self):
        answer = "Короткий ответ.\n\nВторой абзац."
        report = inspect_reading_v3_answer(answer, "career")
        self.assertEqual(answer, "Короткий ответ.\n\nВторой абзац.")
        self.assertIn("word_count:4", report["issues"])
        self.assertIn("paragraph_count:2", report["issues"])

    def test_diagnostics_flag_informal_address(self):
        paragraph = ("Выбор остаётся за вами. " * 7).strip()
        answer = paragraph + "\n\nТебе важно решить самой.\n\nЧто подходит именно вам?"
        report = inspect_reading_v3_answer(answer, "love")
        self.assertIn("informal_address", report["issues"])

    def test_love_diagnostics_accept_all_three_named_cards(self):
        answer = (
            "Солнце отражает тепло контакта.\n\n"
            "Отшельник добавляет тему паузы.\n\n"
            "Умеренность возвращает вопрос к вашей мере."
        )
        report = inspect_reading_v3_answer(
            answer,
            "love",
            ["Солнце", "Отшельник", "Умеренность"],
        )
        self.assertEqual(report["named_card_count"], 3)
        self.assertNotIn("named_cards:3", report["issues"])

    def test_love_diagnostics_flag_missing_third_card(self):
        answer = (
            "Солнце отражает описанное тепло.\n\n"
            "Отшельник добавляет тему паузы.\n\n"
            "Какой формат контакта подходит вам?"
        )
        report = inspect_reading_v3_answer(
            answer,
            "love",
            ["Солнце", "Отшельник", "Умеренность"],
        )
        self.assertEqual(report["named_card_count"], 2)
        self.assertIn("named_cards:2", report["issues"])

    def test_daily_diagnostics_keep_daily_target(self):
        paragraph = ("фокус " * 30).strip()
        report = inspect_reading_v3_answer("\n\n".join([paragraph] * 3), "daily_card")
        self.assertEqual(report["word_count"], 90)
        self.assertTrue(report["within_word_target"])
        self.assertTrue(report["has_expected_paragraphs"])

    def test_generation_makes_exactly_one_ai_call(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return "**Разбор.** Вопрос."

        result = generate_reading_v3(
            spread_type="love",
            user_question="Продолжать контакт?",
            cards=SAMPLE_CARDS[:3],
            topic="love",
            ai_call=fake_ai,
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("Продолжать контакт?", calls[0])
        self.assertEqual(result, "Разбор. Вопрос.")

    def test_empty_ai_answer_returns_empty_without_retry(self):
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
