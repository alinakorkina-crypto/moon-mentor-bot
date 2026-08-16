"""Three-scenario one-call preview for Reading Engine v8."""

from ai_reader_openai_v8 import ask_openai_v8
from reading_engine_v8 import (
    PRICING_AS_OF_V8,
    count_words_v8,
    generate_reading_v8,
    split_paragraphs_v8,
)


SCENARIOS = [
    {
        "title": "ИНИЦИАТИВА",
        "question": "Выйдет тот, о ком я думаю постоянно, первым на контакт?",
        "topic": "general",
        "cards": [
            {
                "name": "Колесница",
                "general": (
                    "Тема инициативы и движения; это не доказательство намерения "
                    "другого человека и не совет пользователю действовать самому."
                ),
            },
            {
                "name": "Башня",
                "general": (
                    "Сильное противоречие, нарушающее прямое развитие импульса; "
                    "это не подтверждённое внешнее событие."
                ),
            },
            {
                "name": "Звезда",
                "general": (
                    "Надежда и открытая возможность, которую важно отличать от "
                    "уже совершённого практического шага."
                ),
            },
        ],
    },
    {
        "title": "ЛИЧНЫЙ ВЫБОР — ОТНОШЕНИЯ",
        "question": (
            "Мы тепло общаемся, но потом он надолго пропадает. "
            "Стоит ли продолжать этот контакт?"
        ),
        "topic": "love",
        "cards": [
            {"name": "Солнце", "love": "Теплота и открытость моментов общения."},
            {
                "name": "Отшельник",
                "love": "Дистанция и паузы без объяснения причин другого человека.",
            },
            {
                "name": "Умеренность",
                "love": "Подходящая пользователю мера и формат связи.",
            },
        ],
    },
    {
        "title": "ЛИЧНЫЙ ВЫБОР — КАРЬЕРА",
        "question": (
            "Мне предлагают новую работу с большей зарплатой, но обязанности пока "
            "описаны расплывчато. Соглашаться?"
        ),
        "topic": "career",
        "cards": [
            {"name": "Колесница", "career": "Движение и профессиональный переход."},
            {"name": "Луна", "career": "Неполная информация и размытые условия."},
            {
                "name": "Император",
                "career": "Структура роли, ответственность и границы полномочий.",
            },
        ],
    },
]


def diagnostic(result) -> str:
    info = result.get("diagnostics") or {}
    usage = info.get("usage") or {}
    cost = info.get("cost_usd")
    cost_text = f"${cost:.6f}" if isinstance(cost, (int, float)) else "—"
    return (
        f"Модель: {info.get('model') or '—'}\n"
        f"Статус: {info.get('status') or '—'}\n"
        f"Входных токенов: {usage.get('input_tokens', '—')}\n"
        f"Кэшированных входных: {usage.get('cached_input_tokens', '—')}\n"
        f"Выходных токенов: {usage.get('output_tokens', '—')}\n"
        f"Reasoning-токенов внутри выхода: {usage.get('reasoning_tokens', '—')}\n"
        f"Всего токенов: {usage.get('total_tokens', '—')}\n"
        f"Расчётная стоимость: {cost_text}\n"
        f"Тарифы зафиксированы на: {PRICING_AS_OF_V8}"
    )


def main() -> None:
    print("\n===== READING ENGINE V8: OPENAI ONE-CALL PREVIEW =====\n")
    for index, scenario in enumerate(SCENARIOS, start=1):
        calls = 0

        def model_call(prompt: str):
            nonlocal calls
            calls += 1
            return ask_openai_v8(prompt)

        result = generate_reading_v8(
            question=scenario["question"],
            cards=scenario["cards"],
            topic=scenario["topic"],
            model_call=model_call,
        )
        print(f"===== TEST {index}: {scenario['title']} =====\n")
        print(f"Вопрос: {scenario['question']}")
        print("Карты: " + " — ".join(card["name"] for card in scenario["cards"]) + "\n")
        print(result["text"])
        print(f"\nМаршрут: {result['route']}")
        print(f"Слов: {count_words_v8(result['text'])}")
        print(f"Абзацев: {len(split_paragraphs_v8(result['text']))}")
        print("Источник: " + ("локальный fallback" if result["used_fallback"] else "OpenAI, один запрос"))
        print(f"Этап: {result['stage']}")
        print("Ошибки: " + (", ".join(result["issues"]) if result["issues"] else "нет"))
        print("Предупреждения: " + (", ".join(result["warnings"]) if result["warnings"] else "нет"))
        print(diagnostic(result))
        if result.get("rejected_text"):
            print("\nОтклонённый AI-текст:\n")
            print(result["rejected_text"])
        print(f"AI-запросов: {calls}")
        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
