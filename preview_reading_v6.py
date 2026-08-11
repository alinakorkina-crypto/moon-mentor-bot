"""Two-route control preview for Reading Engine v6."""

from ai_reader_v6 import ask_gemini_analysis_v6, ask_gemini_editor_v6
from reading_engine_v6 import count_words_v6, generate_reading_v6, split_paragraphs_v6


SCENARIOS = [
    {
        "title": "ИНИЦИАТИВА",
        "question": "Выйдет тот, о ком я думаю постоянно, первым на контакт?",
        "topic": "general",
        "cards": [
            {
                "name": "Колесница",
                "general": (
                    "Тема инициативы, направления и усилия сдвинуть ситуацию; это не "
                    "доказательство намерения другого человека."
                ),
            },
            {
                "name": "Башня",
                "general": (
                    "Сильное противоречие, которое не позволяет читать первый импульс "
                    "как прямой и надёжный; это не подтверждённое событие."
                ),
            },
            {
                "name": "Звезда",
                "general": (
                    "Сохранение возможности и надежды при необходимости отличать "
                    "перспективу от уже оформленного практического шага."
                ),
            },
        ],
    },
    {
        "title": "ЛИЧНЫЙ ВЫБОР",
        "question": (
            "Мы тепло общаемся, но потом он надолго пропадает. "
            "Стоит ли продолжать этот контакт?"
        ),
        "topic": "love",
        "cards": [
            {
                "name": "Солнце",
                "love": "Заметная ценность тёплых и открытых эпизодов общения.",
            },
            {
                "name": "Отшельник",
                "love": (
                    "Дистанция и паузы как описанная часть контакта, без объяснения "
                    "чужих причин."
                ),
            },
            {
                "name": "Умеренность",
                "love": (
                    "Критерий подходящей пользователю меры и формата связи, а не совет "
                    "приспособиться к неудобной динамике."
                ),
            },
        ],
    },
]


def diagnostic(label: str, value) -> str:
    if not value:
        return f"{label}: —"
    usage = value.get("usage") or {}
    return (
        f"{label}: finish_reason={value.get('finish_reason') or '—'}, "
        f"thoughts={usage.get('thoughts_token_count', '—')}, "
        f"output={usage.get('candidates_token_count', '—')}"
    )


def main() -> None:
    print("\n===== READING ENGINE V6.1: PSYCHOLOGICAL ROUTED PREVIEW =====\n")
    for index, scenario in enumerate(SCENARIOS, start=1):
        calls = {"analysis": 0, "editor": 0}

        def analysis_call(prompt: str):
            calls["analysis"] += 1
            return ask_gemini_analysis_v6(prompt)

        def editor_call(prompt: str):
            calls["editor"] += 1
            return ask_gemini_editor_v6(prompt)

        result = generate_reading_v6(
            question=scenario["question"],
            cards=scenario["cards"],
            topic=scenario["topic"],
            analysis_call=analysis_call,
            editor_call=editor_call,
        )
        print(f"===== TEST {index}: {scenario['title']} =====\n")
        print(f"Вопрос: {scenario['question']}")
        print("Карты: " + " — ".join(card["name"] for card in scenario["cards"]) + "\n")
        print(result["text"])
        print(f"\nМаршрут: {result['route']}")
        print(f"Слов: {count_words_v6(result['text'])}")
        print(f"Абзацев: {len(split_paragraphs_v6(result['text']))}")
        print("Источник: " + ("локальный fallback" if result["used_fallback"] else "AI-анализ + AI-редактор"))
        print(f"Этап: {result['stage']}")
        print("Валидация: " + (", ".join(result["issues"]) if result["issues"] else "OK"))
        print(diagnostic("Аналитик", result.get("analysis_diagnostics")))
        print(diagnostic("Редактор", result.get("editor_diagnostics")))
        if result.get("rejected_text"):
            print("\nОтклонённый AI-текст:\n")
            print(result["rejected_text"])
        print(f"AI-запросов: {calls['analysis'] + calls['editor']}")
        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
