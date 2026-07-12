import unittest

from reading_engine_v2 import (
    SPREAD_POSITIONS,
    build_reading_v2_prompt,
    prepare_cards_with_positions,
)


SAMPLE_CARDS = [
    {
        "name": "Солнце",
        "general": "Открытость, ясность и тепло.",
        "love": "В контакте заметны тепло и прямые проявления.",
        "career": "В работе заметны ясность и признание.",
        "question": "Что уже видно достаточно ясно?",
        "advice": "Опирайтесь на прямые факты.",
        "tags": ["warmth", "clarity"],
    },
    {
        "name": "Луна",
        "general": "Неясность, смешанные сигналы и догадки.",
        "love": "В контакте остаётся недосказанность.",
        "career": "В рабочей ситуации не хватает информации.",
        "question": "Что приходится додумывать?",
        "advice": "Отделите факты от предположений.",
        "tags": ["unclear", "signals"],
    },
    {
        "name": "Справедливость",
        "general": "Баланс, факты и договорённости.",
        "love": "Важны взаимность и честные договорённости.",
        "career": "Важны условия, документы и ответственность.",
        "question": "Где нарушен баланс?",
        "advice": "Сравните слова, действия и условия.",
        "tags": ["facts", "balance"],
    },
    {
        "name": "Сила",
        "general": "Выдержка и управляемое напряжение.",
        "love": "В контакте есть притяжение и сдержанность.",
        "career": "Нужны устойчивость и спокойная настойчивость.",
        "question": "Где нужна выдержка?",
        "advice": "Не действуйте из резкого импульса.",
        "tags": ["restraint", "strength"],
    },
]


class ReadingEngineV2Tests(unittest.TestCase):
    def test_01_love_spread_assigns_three_meaningful_positions(self):
        prepared = prepare_cards_with_positions(SAMPLE_CARDS[:3], "love", "love")
        self.assertEqual(
            [item["position"] for item in prepared],
            SPREAD_POSITIONS["love"],
        )

    def test_02_full_spread_keeps_all_four_cards(self):
        prepared = prepare_cards_with_positions(SAMPLE_CARDS, "full", "general")
        self.assertEqual(len(prepared), 4)
        self.assertEqual(prepared[-1]["name"], "Сила")

    def test_03_daily_card_has_daily_position(self):
        prepared = prepare_cards_with_positions(
            SAMPLE_CARDS[:1],
            "daily_card",
            "general",
        )
        self.assertEqual(prepared[0]["position"], "Фокус дня")

    def test_04_extra_cards_receive_fallback_positions(self):
        prepared = prepare_cards_with_positions(
            SAMPLE_CARDS,
            "personal_question",
            "general",
        )
        self.assertEqual(prepared[3]["position"], "Дополнительный акцент 4")

    def test_05_prompt_contains_exact_user_question(self):
        question = "Почему после тёплого общения снова появляется дистанция?"
        prompt = build_reading_v2_prompt(
            "love",
            question,
            SAMPLE_CARDS[:3],
            "love",
        )
        self.assertIn(question, prompt)

    def test_06_prompt_contains_every_card_and_position(self):
        prompt = build_reading_v2_prompt(
            "full",
            "Общий расклад",
            SAMPLE_CARDS,
            "general",
        )
        for card in SAMPLE_CARDS:
            self.assertIn(card["name"], prompt)
        for position in SPREAD_POSITIONS["full"]:
            self.assertIn(position, prompt)

    def test_07_love_topic_uses_love_meanings(self):
        prompt = build_reading_v2_prompt(
            "love",
            "Что видно в нашем общении?",
            SAMPLE_CARDS[:3],
            "love",
        )
        self.assertIn(SAMPLE_CARDS[0]["love"], prompt)
        self.assertIn(SAMPLE_CARDS[1]["love"], prompt)

    def test_08_career_topic_uses_career_meanings(self):
        prompt = build_reading_v2_prompt(
            "career",
            "Стоит ли менять работу?",
            SAMPLE_CARDS[:3],
            "career",
        )
        self.assertIn(SAMPLE_CARDS[0]["career"], prompt)
        self.assertIn("возможности, ограничения, противоречия", prompt)

    def test_09_relationship_prompt_forbids_mind_reading(self):
        prompt = build_reading_v2_prompt(
            "love",
            "Что он чувствует?",
            SAMPLE_CARDS[:3],
            "love",
        )
        self.assertIn(
            "Не угадывайте чувства другого человека",
            prompt,
        )
        self.assertIn(
            "Утверждать как факт, что другой человек думает",
            prompt,
        )

    def test_10_daily_prompt_uses_short_daily_structure(self):
        prompt = build_reading_v2_prompt(
            "daily_card",
            "Карта дня",
            SAMPLE_CARDS[:1],
            "general",
        )
        self.assertIn("🃏 Фокус дня", prompt)
        self.assertIn("🌙 Как это может проявиться", prompt)
        self.assertIn("100–160 слов", prompt)

    def test_11_multi_card_prompt_requires_combination_reading(self):
        prompt = build_reading_v2_prompt(
            "personal_question",
            "Что мне важно понять?",
            SAMPLE_CARDS[:3],
            "general",
        )
        self.assertIn("Покажите взаимодействие карт", prompt)
        self.assertIn("не перечень значений карт", prompt)

    def test_12_prompt_requires_telegram_ready_output(self):
        prompt = build_reading_v2_prompt(
            "personal_question",
            "Что мне важно понять?",
            SAMPLE_CARDS[:3],
            "general",
        )
        self.assertIn("Короткие абзацы, удобные для Telegram", prompt)
        self.assertIn('Обращение к пользователю на "вы"', prompt)
        self.assertIn("Выведите только готовый расклад", prompt)


if __name__ == "__main__":
    unittest.main()
