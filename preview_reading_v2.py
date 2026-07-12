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
                "love": "Символика тепла, открытости, заметности и удовольствия от контакта.",
                "question": "Какие наблюдаемые эпизоды пользователь связывает с теплом?",
                "advice": "Сопоставьте яркость отдельных эпизодов с общей динамикой.",
                "tags": ["warmth", "openness", "joy"],
            },
            {
                "name": "Отшельник",
                "general": "Дистанция, пауза, замедление и обращение к собственному пространству.",
                "love": "Символика дистанции, паузы, отдельности и замедления контакта.",
                "question": "Как в описании пользователя соотносятся контакт и паузы?",
                "advice": "Опишите ритм только по сведениям из вопроса.",
                "tags": ["distance", "pause", "solitude"],
            },
            {
                "name": "Умеренность",
                "general": "Мера, постепенность, спокойный темп и соединение различий.",
                "love": "Символика меры, постепенности, согласования разных темпов и сохранения баланса.",
                "question": "Какой темп пользователь считает для себя приемлемым?",
                "advice": "Сравните вклад пользователя с наблюдаемым развитием контакта.",
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
                "career": "Символика движения, амбиции, перехода и управления выбранным направлением.",
                "question": "Куда именно ведёт этот переход?",
                "advice": "Свяжите возможность перехода с заявленной целью пользователя.",
                "tags": ["movement", "ambition", "direction"],
            },
            {
                "name": "Луна",
                "general": "Неясность, смешанные сигналы и недостаток проверяемой информации.",
                "career": "Символика неясности, неполной информации и неоднозначных условий.",
                "question": "Каких условий вы пока не знаете?",
                "advice": "Назовите, какие данные можно проверить до решения.",
                "tags": ["uncertainty", "missing_information", "risk"],
            },
            {
                "name": "Император",
                "general": "Структура, ответственность, правила, полномочия и границы.",
                "career": "Символика структуры, полномочий, ответственности, правил и границ роли.",
                "question": "Какие договорённости сделают роль управляемой?",
                "advice": "Переведите символику структуры в проверяемые условия предложения.",
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
                "advice": "Не определяйте причину паузы без слов пользователя.",
                "tags": ["pause", "perspective", "stagnation"],
            },
            {
                "name": "Башня",
                "general": "Разрушение неработающей конструкции, резкая ясность и освобождение от иллюзии устойчивости.",
                "question": "Какой элемент ситуации пользователь уже считает неработающим или неустойчивым?",
                "advice": "Рассматривайте изменение одного элемента, не предполагая необходимость разрушить всё.",
                "tags": ["change", "truth", "release"],
            },
            {
                "name": "Звезда",
                "general": "Ориентир, восстановление, честная надежда и направление, которое возвращает живость.",
                "question": "Какие занятия или направления пользователь связывает с энергией и смыслом?",
                "advice": "Предложите небольшой проверяемый эксперимент вместо окончательного решения.",
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
