"""Manual comparison preview for the isolated Reading Engine v3 experiment.

The script makes one AI request per scenario and does not import main.py or
Reading Engine v2.
"""

from ai_reader import ask_gemini
from reading_engine_v3 import generate_reading_v3


SCENARIOS = [
    {
        "title": "ОТНОШЕНИЯ",
        "spread_type": "love",
        "topic": "love",
        "question": (
            "Мы тепло общаемся, но потом он надолго пропадает. "
            "Стоит ли продолжать этот контакт?"
        ),
        "cards": [
            {
                "name": "Солнце",
                "general": "Тепло, открытость и ясное проявление.",
                "love": "Тепло, открытость и удовольствие от контакта.",
            },
            {
                "name": "Отшельник",
                "general": "Дистанция, пауза и замедление.",
                "love": "Дистанция, пауза и отдельный ритм контакта.",
            },
            {
                "name": "Умеренность",
                "general": "Мера, постепенность и согласование темпа.",
                "love": "Мера, постепенность и баланс участия.",
            },
        ],
    },
    {
        "title": "КАРЬЕРА",
        "spread_type": "career",
        "topic": "career",
        "question": (
            "Мне предлагают новую работу с большей зарплатой, но обязанности "
            "пока описаны расплывчато. Соглашаться?"
        ),
        "cards": [
            {
                "name": "Колесница",
                "general": "Движение, амбиция и управление направлением.",
                "career": "Переход, движение и управление выбранным направлением.",
            },
            {
                "name": "Луна",
                "general": "Неясность и недостаток проверяемой информации.",
                "career": "Неполная информация и неоднозначные условия.",
            },
            {
                "name": "Император",
                "general": "Структура, правила, полномочия и границы.",
                "career": "Структура роли, ответственность и ясные полномочия.",
            },
        ],
    },
]


def card_names(cards: list[dict]) -> str:
    return " — ".join(card["name"] for card in cards)


def count_words(text: str) -> int:
    return len(text.split())


def main() -> None:
    print("\n===== READING ENGINE V3: 2-SCENARIO COMPARISON =====\n")

    for index, scenario in enumerate(SCENARIOS, start=1):
        calls = 0

        def one_counted_call(prompt: str) -> str | None:
            nonlocal calls
            calls += 1
            return ask_gemini(prompt)

        print(f"===== TEST {index}: {scenario['title']} =====\n")
        print(f"Вопрос: {scenario['question']}")
        print(f"Карты: {card_names(scenario['cards'])}\n")

        answer = generate_reading_v3(
            spread_type=scenario["spread_type"],
            user_question=scenario["question"],
            cards=scenario["cards"],
            topic=scenario["topic"],
            ai_call=one_counted_call,
        )

        if not answer:
            print("Vertex AI не вернул ответ.\n")
        else:
            print(answer)
            print(f"\nСлов: {count_words(answer)}")
            print(f"AI-запросов: {calls}")

        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
