"""Two-scenario preview for best-of-two Reading Engine v4.5."""

import re

from ai_reader_v45 import ask_gemini_v45
from preview_reading_v4 import SCENARIOS
from reading_engine_v45 import generate_reading_v45


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?", text))


def main() -> None:
    print("\n===== READING ENGINE V4.5: BEST-OF-TWO 2-SCENARIO PREVIEW =====\n")
    for index, scenario in enumerate(SCENARIOS, start=1):
        calls = 0
        def one_counted_call(prompt: str) -> str | None:
            nonlocal calls
            calls += 1
            return ask_gemini_v45(prompt)

        print(f"===== TEST {index}: {scenario['title']} =====\n")
        print(f"Вопрос: {scenario['question']}")
        print("Карты: " + " — ".join(card["name"] for card in scenario["cards"]) + "\n")
        result = generate_reading_v45(
            spread_type=scenario["spread_type"],
            user_question=scenario["question"],
            cards=scenario["cards"],
            topic=scenario["topic"],
            ai_call=one_counted_call,
        )
        print(result["text"])
        print(f"\nСлов: {count_words(result['text'])}")
        print(f"Абзацев: {len(result['text'].split(chr(10) + chr(10)))}")
        print("Источник: " + ("локальный fallback" if result["used_fallback"] else "лучший из двух AI-вариантов"))
        print("Выбран вариант: " + (str(result["selected_variant"]) if result["selected_variant"] else "—"))
        print("Оценка селектора: " + (str(result["score"]) if result["score"] is not None else "—"))
        print("Предупреждения: " + (", ".join(result["warnings"]) if result["warnings"] else "нет"))
        print("Валидация: " + (", ".join(result["issues"]) if result["issues"] else "OK"))
        print(f"AI-запросов: {calls}")
        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
