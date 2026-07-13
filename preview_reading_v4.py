"""Two-scenario preview for structured Reading Engine v4."""

import re

from ai_reader_v4 import ask_gemini_v4
from reading_engine_v4 import generate_reading_v4


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
                "love": "Тепло и открытость контакта, заметные в описанном общении.",
            },
            {
                "name": "Отшельник",
                "general": "Дистанция, пауза и замедление.",
                "love": "Пауза и дистанция как наблюдаемая часть рисунка, без объяснения причин.",
            },
            {
                "name": "Умеренность",
                "general": "Мера, постепенность и согласование.",
                "love": "Подходящая пользователю мера участия и формат контакта.",
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
                "general": "Движение и управление направлением.",
                "career": "Сам факт рассматриваемого перехода, без обещания роста или успеха.",
            },
            {
                "name": "Луна",
                "general": "Неясность и недостаток проверяемой информации.",
                "career": "Недостаток конкретной информации об обязанностях, без скрытой угрозы.",
            },
            {
                "name": "Император",
                "general": "Структура, правила и полномочия.",
                "career": "Структура роли, ответственность, полномочия и подчинение.",
            },
        ],
    },
]


def count_words(text: str) -> int:
    return len(
        re.findall(
            r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?",
            text,
        )
    )


def main() -> None:
    print("\n===== READING ENGINE V4: STRUCTURED 2-SCENARIO PREVIEW =====\n")

    for index, scenario in enumerate(SCENARIOS, start=1):
        calls = 0

        def one_counted_call(prompt: str) -> str | None:
            nonlocal calls
            calls += 1
            return ask_gemini_v4(prompt)

        print(f"===== TEST {index}: {scenario['title']} =====\n")
        print(f"Вопрос: {scenario['question']}")
        print(
            "Карты: "
            + " — ".join(card["name"] for card in scenario["cards"])
            + "\n"
        )

        result = generate_reading_v4(
            spread_type=scenario["spread_type"],
            user_question=scenario["question"],
            cards=scenario["cards"],
            topic=scenario["topic"],
            ai_call=one_counted_call,
        )

        print(result["text"])
        print(f"\nСлов: {count_words(result['text'])}")
        print(f"Абзацев: {len(result['text'].split(chr(10) + chr(10)))}")
        print("Источник: " + ("локальный fallback" if result["used_fallback"] else "AI JSON"))
        print(
            "Валидация: "
            + (", ".join(result["issues"]) if result["issues"] else "OK")
        )
        print(f"AI-запросов: {calls}")
        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
