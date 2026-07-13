"""Two-scenario preview for Reading Engine v4.2."""

import re

from ai_reader_v42 import ask_gemini_v42
from preview_reading_v4 import SCENARIOS
from reading_engine_v42 import generate_reading_v42


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?", text))


def main() -> None:
    print("\n===== READING ENGINE V4.2: MORPHOLOGY-AWARE 2-SCENARIO PREVIEW =====\n")
    for index, scenario in enumerate(SCENARIOS, start=1):
        calls = 0
        def one_counted_call(prompt: str) -> str | None:
            nonlocal calls
            calls += 1
            return ask_gemini_v42(prompt)

        print(f"===== TEST {index}: {scenario['title']} =====\n")
        print(f"Вопрос: {scenario['question']}")
        print("Карты: " + " — ".join(card["name"] for card in scenario["cards"]) + "\n")
        result = generate_reading_v42(
            spread_type=scenario["spread_type"],
            user_question=scenario["question"],
            cards=scenario["cards"],
            topic=scenario["topic"],
            ai_call=one_counted_call,
        )
        print(result["text"])
        print(f"\nСлов: {count_words(result['text'])}")
        print(f"Абзацев: {len(result['text'].split(chr(10) + chr(10)))}")
        print("Источник: " + ("локальный fallback" if result["used_fallback"] else "AI JSON + готовый текст"))
        print("Валидация: " + (", ".join(result["issues"]) if result["issues"] else "OK"))
        print(f"AI-запросов: {calls}")
        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
