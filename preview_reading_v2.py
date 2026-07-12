"""Manual quality preview for Reading Engine v2.

This script is not imported by the Telegram bot. It runs three independent
scenarios to test answer quality outside the exemplar included in the prompt.
"""

from ai_reader import ask_gemini
from reading_engine_v2 import build_reading_v2_prompt


SCENARIOS = [
    {
        "title": "ОТНОШЕНИЯ",
        "spread_type": "love",
        "topic": "love",
        "question": "Мы тепло общаемся, но потом он надолго пропадает. Стоит ли продолжать этот контакт?",
        "cards": [
            {
                "name": "Солнце",
                "general": "Тепло, открытость, заметная радость и ясное проявление.",
                "love": "В контакте есть живое тепло, удовольствие от общения и моменты открытости.",
                "question": "Что в этом контакте действительно приносит тепло?",
                "advice": "Отделите приятный эпизод от устойчивой динамики.",
                "tags": ["warmth", "openness", "joy"],
            },
            {
                "name": "Отшельник",
                "general": "Дистанция, пауза, замедление и обращение к собственному пространству.",
                "love": "Напряжение создают дистанция, редкий контакт или несовпадение темпа сближения.",
                "question": "Как часто близость сменяется дистанцией?",
                "advice": "Заметьте реальный ритм контакта.",
                "tags": ["distance", "pause", "solitude"],
            },
            {
                "name": "Умеренность",
                "general": "Мера, постепенность, спокойный темп и соединение различий.",
                "love": "Опорой может стать неспешный темп без попытки ускорить или удержать контакт.",
                "question": "Какой темп общения будет бережным для вас?",
                "advice": "Не вкладывайте больше, чем контакт способен поддержать сейчас.",
                "tags": ["pace", "balance", "patience"],
            },
        ],
    },
    {
        "title": "КАРЬЕРА",
        "spread_type": "career",
        "topic": "career",
        "question": "Мне предлагают новую работу с большей зарплатой, но обязанности пока описаны расплывчато. Соглашаться?",
        "cards": [
            {
                "name": "Колесница",
                "general": "Движение, амбиция, управление направлением и быстрый переход.",
                "career": "Ситуация содержит возможность заметного продвижения и требует самостоятельного управления курсом.",
                "question": "Куда именно ведёт этот переход?",
                "advice": "Определите цель смены работы.",
                "tags": ["movement", "ambition", "direction"],
            },
            {
                "name": "Луна",
                "general": "Неясность, смешанные сигналы и недостаток проверяемой информации.",
                "career": "Главное препятствие — размытые условия, неизвестные ожидания или неполная картина роли.",
                "question": "Каких условий вы пока не знаете?",
                "advice": "Запросите конкретику до решения.",
                "tags": ["uncertainty", "missing_information", "risk"],
            },
            {
                "name": "Император",
                "general": "Структура, ответственность, правила, полномочия и границы.",
                "career": "Направление действия — прояснить зону ответственности, руководителя, полномочия и критерии результата.",
                "question": "Какие договорённости сделают роль управляемой?",
                "advice": "Зафиксируйте ключевые условия письменно.",
                "tags": ["structure", "authority", "boundaries"],
            },
        ],
    },
    {
        "title": "ОБЩИЙ ВОПРОС",
        "spread_type": "personal_question",
        "topic": "general",
        "question": "Я чувствую, что застряла, но не понимаю, что именно нужно менять первым.",
        "cards": [
            {
                "name": "Повешенный",
                "general": "Пауза, прежний взгляд перестаёт работать, необходимость увидеть ситуацию иначе.",
                "question": "Где ожидание уже не даёт нового результата?",
                "advice": "Назовите одну область, в которой вы дольше всего откладываете решение.",
                "tags": ["pause", "perspective", "stagnation"],
            },
            {
                "name": "Башня",
                "general": "Разрушение неработающей конструкции, резкая ясность и освобождение от иллюзии устойчивости.",
                "question": "Какая конструкция держится только потому, что страшно её пересмотреть?",
                "advice": "Не ломайте всё сразу; найдите один элемент, который уже явно не работает.",
                "tags": ["change", "truth", "release"],
            },
            {
                "name": "Звезда",
                "general": "Ориентир, восстановление, честная надежда и направление, которое возвращает живость.",
                "question": "Что возвращает вам ощущение смысла и движения?",
                "advice": "Сделайте небольшой шаг к тому, что даёт энергию, и оцените эффект.",
                "tags": ["hope", "direction", "renewal"],
            },
        ],
    },
]


def card_names(cards: list[dict]) -> str:
    return " — ".join(card["name"] for card in cards)


def main() -> None:
    print("\n===== READING ENGINE V2: 3 CONTROL TESTS =====\n")

    for index, scenario in enumerate(SCENARIOS, start=1):
        print(f"===== TEST {index}: {scenario['title']} =====\n")
        print(f"Вопрос: {scenario['question']}")
        print(f"Карты: {card_names(scenario['cards'])}\n")

        prompt = build_reading_v2_prompt(
            spread_type=scenario["spread_type"],
            user_question=scenario["question"],
            cards=scenario["cards"],
            topic=scenario["topic"],
        )
        answer = ask_gemini(prompt)

        if not answer:
            print("Vertex AI не вернул ответ для этого сценария.\n")
            continue

        print(answer.strip())
        print(f"\n===== END TEST {index} =====\n")


if __name__ == "__main__":
    main()
