"""Control preview for the two-pass personal-question Reading Engine v5."""

from ai_reader_v5 import ask_gemini_analysis_v5, ask_gemini_editor_v5
from reading_engine_v5 import count_words_v5, generate_personal_reading_v5


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


def main() -> None:
    calls = {"analysis": 0, "editor": 0}

    def analysis_call(prompt: str) -> str | None:
        calls["analysis"] += 1
        return ask_gemini_analysis_v5(prompt)

    def editor_call(prompt: str) -> str | None:
        calls["editor"] += 1
        return ask_gemini_editor_v5(prompt)

    result = generate_personal_reading_v5(
        user_question=QUESTION,
        cards=CARDS,
        analysis_call=analysis_call,
        editor_call=editor_call,
    )

    print("\n===== READING ENGINE V5: TWO-PASS PERSONAL QUESTION =====\n")
    print(f"Вопрос: {QUESTION}")
    print("Карты: " + " — ".join(card["name"] for card in CARDS) + "\n")
    print(result["text"])
    print(f"\nСлов: {count_words_v5(result['text'])}")
    print(f"Абзацев: {len(result['text'].split(chr(10) + chr(10)))}")
    print("Источник: " + ("локальный fallback" if result["used_fallback"] else "AI-анализ + AI-редактор"))
    print(f"Этап: {result['stage']}")
    print("Валидация: " + (", ".join(result["issues"]) if result["issues"] else "OK"))
    print(f"AI-запросов: {calls['analysis'] + calls['editor']}")


if __name__ == "__main__":
    main()
