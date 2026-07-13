import unittest

from reading_engine_v3 import (
    build_reading_v3_prompt,
    clean_reading_v3_answer,
    generate_reading_v3,
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
]


class ReadingEngineV3Tests(unittest.TestCase):
    def test_prompt_contains_exact_question_and_all_cards(self):
        question = "Стоит ли продолжать этот контакт?"
        prompt = build_reading_v3_prompt(
            "love",
            question,
            SAMPLE_CARDS,
            "love",
        )
        self.assertIn(question, prompt)
        for card in SAMPLE_CARDS:
            self.assertIn(card["name"], prompt)

    def test_prompt_requires_180_to_220_words(self):
        prompt = build_reading_v3_prompt(
            "career",
            "Соглашаться ли на новую работу?",
            SAMPLE_CARDS,
            "career",
        )
        self.assertIn("Объём строго 180–220 слов", prompt)

    def test_prompt_requires_direct_answer_and_central_dilemma(self):
        prompt = build_reading_v3_prompt(
            "love",
            "Продолжать общение?",
            SAMPLE_CARDS,
            "love",
        )
        self.assertIn("Начни с прямого ответа", prompt)
        self.assertIn("одну центральную дилемму", prompt)

    def test_prompt_requires_observable_criterion_and_next_step(self):
        prompt = build_reading_v3_prompt(
            "career",
            "Принимать предложение?",
            SAMPLE_CARDS,
            "career",
        )
        self.assertIn("один наблюдаемый критерий", prompt)
        self.assertIn("одним конкретным следующим шагом", prompt)

    def test_prompt_forbids_separate_card_retellings(self):
        prompt = build_reading_v3_prompt(
            "love",
            "Что важно увидеть?",
            SAMPLE_CARDS,
            "love",
        )
        self.assertIn(
            "Не создавай отдельный абзац или мини-толкование для каждой карты",
            prompt,
        )
        self.assertIn("Не перечисляй карты по очереди", prompt)

    def test_topic_meanings_are_used(self):
        prepared = prepare_cards_v3(SAMPLE_CARDS, "career", "career")
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

    def test_generation_makes_exactly_one_ai_call(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return "**Прямой ответ.** Следующий шаг."

        result = generate_reading_v3(
            spread_type="love",
            user_question="Продолжать контакт?",
            cards=SAMPLE_CARDS,
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
            cards=SAMPLE_CARDS,
            topic="career",
            ai_call=fake_ai,
        )

        self.assertEqual(result, "")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
