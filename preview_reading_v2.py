"""One-off quality preview for Reading Engine v2.

This script is not imported by the Telegram bot. Run it manually to compare a
single Vertex AI response against the current reading engine.
"""

from ai_reader import ask_gemini
from reading_engine_v2 import build_reading_v2_prompt


QUESTION = "Не понимаю, писать ему первой или нет?"


CARDS = [
    {
        "name": "Маг",
        "general": (
            "Со стороны заметна активность, инициатива, умение привлекать внимание "
            "и задавать тон общению. Поведение может выглядеть уверенным и собранным."
        ),
        "love": (
            "В отношениях Маг показывает активную подачу, инициативу, яркое проявление "
            "или попытку задавать тон общению. Контакт может быть живым, но важно "
            "смотреть на действия, а не только на слова."
        ),
        "question": "Кто сейчас задаёт тон ситуации — словами, действиями или инициативой?",
        "advice": "Отделите реальную инициативу от красивой подачи.",
        "tags": ["initiative", "action", "communication"],
    },
    {
        "name": "Луна",
        "general": (
            "Со стороны можно легко запутаться: разные сигналы могут противоречить "
            "друг другу."
        ),
        "love": (
            "В отношениях Луна показывает неясность, смешанные сигналы, "
            "недоговорённость и риск додумывать за другого человека. "
            "Лучше отделять факты от ощущений."
        ),
        "question": "Что здесь факт, а что только догадка?",
        "advice": "Не достраивайте смысл там, где пока мало данных.",
        "tags": ["unclear", "mixed_signals", "fog"],
    },
    {
        "name": "Справедливость",
        "general": (
            "Со стороны это выглядит как необходимость ясности, баланса, честных "
            "правил, фактов и конкретных договорённостей."
        ),
        "love": (
            "В отношениях Справедливость показывает вопрос баланса: кто проявляется, "
            "кто ждёт, где есть взаимность, а где контакт держится на догадках."
        ),
        "question": "Какие факты здесь важнее впечатлений?",
        "advice": "Сравните слова, действия и договорённости.",
        "tags": ["facts", "balance", "clarity"],
    },
]


def main() -> None:
    prompt = build_reading_v2_prompt(
        spread_type="love",
        user_question=QUESTION,
        cards=CARDS,
        topic="love",
    )

    print("\n===== READING ENGINE V2 PREVIEW =====\n")
    print(f"Вопрос: {QUESTION}")
    print("Карты: Маг — Луна — Справедливость\n")

    answer = ask_gemini(prompt)

    if not answer:
        raise SystemExit("Vertex AI не вернул ответ. Проверьте журнал ошибки выше.")

    print(answer.strip())
    print("\n===== END PREVIEW =====\n")


if __name__ == "__main__":
    main()
