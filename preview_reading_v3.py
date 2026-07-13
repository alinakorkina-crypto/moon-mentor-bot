"""Manual preview for the isolated Reading Engine v3.6 experiment.

By default the script keeps the low-cost two-scenario comparison (love and
career). Other spread types can be selected explicitly from the command line.
Each selected scenario makes exactly one AI request.
"""

import argparse
import re

from ai_reader import ask_gemini
from reading_engine_v3 import generate_reading_v3, inspect_reading_v3_answer


SCENARIOS = [
    {
        "key": "love",
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
                "love": "Символика тепла, открытости и удовольствия от контакта.",
            },
            {
                "name": "Отшельник",
                "general": "Дистанция, пауза и замедление.",
                "love": "Символика дистанции, паузы и отдельности.",
            },
            {
                "name": "Умеренность",
                "general": "Мера, постепенность и согласование темпа.",
                "love": "Символика меры, постепенности и баланса участия.",
            },
        ],
    },
    {
        "key": "career",
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
    {
        "key": "personal",
        "title": "СВОЙ ВОПРОС",
        "spread_type": "personal_question",
        "topic": "general",
        "question": "Я застряла и не понимаю, что нужно менять первым.",
        "cards": [
            {
                "name": "Повешенный",
                "general": "Пауза и необходимость посмотреть на ситуацию иначе.",
            },
            {
                "name": "Башня",
                "general": "Сбой прежней конструкции и резкое изменение взгляда.",
            },
            {
                "name": "Звезда",
                "general": "Ориентир, надежда и постепенное восстановление направления.",
            },
        ],
    },
    {
        "key": "daily",
        "title": "КАРТА ДНЯ",
        "spread_type": "daily_card",
        "topic": "general",
        "question": "Какой символический фокус дня предлагает карта?",
        "cards": [
            {
                "name": "Сила",
                "general": "Выдержка, мягкая устойчивость и управление импульсом.",
            },
        ],
    },
    {
        "key": "full",
        "title": "ПОЛНЫЙ РАСКЛАД",
        "spread_type": "full",
        "topic": "general",
        "question": (
            "Пользователь выбрал полный расклад без отдельного вопроса. "
            "Дайте общий символический обзор без выдумывания обстоятельств."
        ),
        "cards": [
            {
                "name": "Смерть",
                "general": "Смена формата и завершение прежнего этапа.",
            },
            {
                "name": "Луна",
                "general": "Неясность и недостаток проверяемой информации.",
            },
            {
                "name": "Императрица",
                "general": "Поддержка, рост и создание более живых условий.",
            },
            {
                "name": "Мир",
                "general": "Границы, завершённость и оформленный результат.",
            },
        ],
    },
]


def card_names(cards: list[dict]) -> str:
    return " — ".join(card["name"] for card in cards)


def count_words(text: str) -> int:
    return len(
        re.findall(
            r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?",
            text,
        )
    )


def select_scenarios(selection: str) -> list[dict]:
    if selection == "core":
        return [item for item in SCENARIOS if item["key"] in {"love", "career"}]
    if selection == "all":
        return SCENARIOS
    return [item for item in SCENARIOS if item["key"] == selection]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=["core", "all", "love", "career", "personal", "daily", "full"],
        default="core",
        help="core keeps the default two-request love/career comparison",
    )
    return parser.parse_args()


def main() -> None:
    selected = select_scenarios(parse_args().scenario)
    print(
        f"\n===== READING ENGINE V3.6: {len(selected)} CONTROL SCENARIO(S) =====\n"
    )

    for index, scenario in enumerate(selected, start=1):
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
            report = inspect_reading_v3_answer(answer, scenario["spread_type"])
            print(f"\nСлов: {count_words(answer)}")
            print(f"Абзацев: {report['paragraph_count']}")
            print(
                "Формат: "
                + ("OK" if not report["issues"] else ", ".join(report["issues"]))
            )
            print(f"AI-запросов: {calls}")

        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
