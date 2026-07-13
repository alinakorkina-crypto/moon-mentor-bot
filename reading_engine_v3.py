"""Experimental one-call Reading Engine v3.9 for Moon Mentor.

The module is isolated from main.py and Reading Engine v2. It builds a compact
topic-aware prompt, makes exactly one AI call, and only removes Markdown
emphasis markers from the returned text.
"""

import re
from typing import Any, Callable


SYSTEM_INSTRUCTION_V3 = """
Вы — редактор Moon Mentor. Создавайте символические разборы Таро как инструмент
размышления, а не как предсказание или способ узнать мысли другого человека.

Приоритетные правила:
1. Фактами считайте только сведения из раздела «Вопрос пользователя». Значения карт
   — символические ракурсы: они не подтверждают искренность, причины, намерения,
   устойчивость, риск, успех или будущие события.
2. Отвечайте на суть вопроса в первом предложении через ключевое условие выбора.
   Не принимайте решение за пользователя и не подталкивайте его к одному варианту.
3. В многокарточном раскладе используйте все карты и позиции, но создавайте один
   общий вывод. Каждая следующая карта должна уточнять или менять предыдущую мысль,
   а не получать отдельный пересказ.
4. Не объясняйте мотивы и внутреннее состояние людей. Не усиливайте неопределённость
   и не превращайте неудобный формат ситуации в норму, к которой нужно приспособиться.
5. Показывайте только наблюдаемые признаки и сведения, способные добавить ясности.
   Окончательный выбор всегда остаётся за пользователем.
6. Начинайте сразу с ответа — без приветствия, представления и вводной фразы.
   Пишите на «вы», легко, тепло и естественно. Избегайте канцелярита, драматизации,
   эзотерического пафоса, повторов и Markdown-звёздочек.

Перед выдачей молча проверьте соответствие этим правилам. Верните только готовый текст.
""".strip()


SPREAD_POSITIONS = {
    "daily_card": (
        "Фокус дня",
    ),
    "love": (
        "Что видно в контакте",
        "Центральное напряжение",
        "Практический ориентир",
    ),
    "career": (
        "Возможность",
        "Неясность или ограничение",
        "Условие решения",
    ),
    "personal_question": (
        "Центр вопроса",
        "Что важно увидеть",
        "На что опереться",
    ),
    "full": (
        "Центральная тема",
        "Что осложняет ситуацию",
        "Что поддерживает",
        "Куда направить внимание",
    ),
}


SPREAD_INSTRUCTIONS = {
    "daily_card": (
        "Дайте один символический фокус дня, одно возможное бытовое проявление "
        "и один вопрос для наблюдения. Не предсказывайте событие дня."
    ),
    "love": (
        "Перед ответом молча разделите известное и неизвестное. Известны только прямо "
        "описанные пользователем эпизоды и действия; причины, искренность, намерения и "
        "будущая устойчивость контакта неизвестны. Дайте ясный ответ по существу: "
        "объясните, от какого наблюдаемого условия зависит смысл продолжения контакта "
        "для самого пользователя, но не выбирайте за него. Центральная мысль — различие "
        "между теплом отдельных эпизодов и устойчивостью связи. Используйте все три "
        "карты: первая раскрывает видимую часть контакта, вторая — напряжение, третья "
        "меняет общий вывод и возвращает его к границам пользователя. Соберите их в "
        "одну линию, а не в три последовательных толкования."
    ),
    "career": (
        "Отвечайте на основании фактов из вопроса, а не карьерных метафор. Большая "
        "зарплата — названное преимущество; расплывчатые обязанности — недостаток "
        "информации, а не обещание развития, скрытый риск или туман. Сразу объясните, "
        "каких данных не хватает, чтобы пользователь мог оценить предложение сам. "
        "Свяжите все карты в один вывод о движении, неопределённости и необходимой "
        "структуре, не пересказывая их по очереди. Конкретизируйте обязанности, полномочия, "
        "подчинение и ожидаемые результаты. Не решайте за пользователя и не обещайте успех."
    ),
    "personal_question": (
        "Сфокусируйтесь на одной дилемме пользователя. Если вопрос слишком широкий, "
        "не придумывайте сферу или обстоятельства: прямо назовите, какого контекста "
        "не хватает для индивидуального вывода."
    ),
    "full": (
        "Свяжите четыре позиции в последовательность: центральная тема, осложнение, "
        "опора и направление внимания. Не утверждайте, что случайный расклад описывает "
        "всю жизнь пользователя или гарантирует новый этап."
    ),
}


LOVE_STRUCTURE = """
Напишите три лёгких абзаца без заголовков:
1. Первым предложением прямо объясните, от чего для пользователя зависит ответ
   на его вопрос. Затем нейтрально назовите только описанные факты.
2. Дайте единое толкование сочетания всех трёх карт. Назовите каждую карту, но
   покажите, как третья карта меняет общий вывод, а не пересказывайте значения по очереди.
3. Назовите один наблюдаемый аспект взаимности и завершите мягким вопросом о
   формате контакта, который соответствует потребностям пользователя.

Общий объём — 110–145 слов. Не повторяйте одну мысль и не давайте указаний.
""".strip()


CAREER_STRUCTURE = """
Напишите три ясных абзаца без заголовков:
1. Первым предложением ответьте по существу: сейчас выбор упирается в конкретный
   недостаток информации. Назовите преимущество и неопределённую часть предложения.
2. Соберите все карты в один вывод о том, что позволяет оценить роль. Не обещайте
   развитие, успех или возможность изменить условия после выхода.
3. Назовите конкретные сведения, которые добавят ясности, и завершите одним
   вопросом о приоритете пользователя, не подталкивая к одному варианту.

Общий объём — 130–170 слов. Не выносите решение за пользователя.
""".strip()


MULTI_CARD_STRUCTURE = """
Напишите три естественных абзаца без заголовков:
1. Ясно назовите главный рисунок ситуации и напряжение выбора, не давая вердикта.
2. Свяжите карты с конкретным вопросом в одну мысль.
3. Покажите, какой факт или наблюдение может добавить ясности, и завершите одним
   мягким, точным вопросом для самостоятельного решения.

Общий объём — 130–170 слов. Не растягивайте мысль ради объёма.
""".strip()

DAILY_STRUCTURE = """
Напишите три коротких абзаца без заголовков:
1. Центральная символическая тема карты.
2. Одно возможное бытовое проявление без предсказания.
3. Один небольшой ориентир и один вопрос для наблюдения.

Общий объём — 90–130 слов.
""".strip()


def prepare_cards_v3(
    cards: list[dict[str, Any]],
    spread_type: str,
    topic: str = "general",
) -> list[dict[str, str]]:
    """Keep only the card data needed by the compact v3 prompt."""
    positions = SPREAD_POSITIONS.get(
        spread_type,
        SPREAD_POSITIONS["personal_question"],
    )
    prepared: list[dict[str, str]] = []

    for index, card in enumerate(cards):
        position = (
            positions[index]
            if index < len(positions)
            else f"Дополнительный акцент {index + 1}"
        )
        prepared.append(
            {
                "position": position,
                "name": card["name"],
                "meaning": card.get(topic, card.get("general", "")),
            }
        )

    return prepared


def format_cards_v3(cards: list[dict[str, str]]) -> str:
    """Format cards as compact source material, not ready-made paragraphs."""
    return "\n".join(
        f"- {card['position']}: {card['name']} — {card['meaning']}"
        for card in cards
    )


def build_reading_v3_prompt(
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    topic: str = "general",
) -> str:
    """Build the concise task data sent under the v3 system instruction."""
    cards_text = format_cards_v3(prepare_cards_v3(cards, spread_type, topic))
    spread_instruction = SPREAD_INSTRUCTIONS.get(
        spread_type,
        SPREAD_INSTRUCTIONS["personal_question"],
    )
    output_structure = {
        "daily_card": DAILY_STRUCTURE,
        "love": LOVE_STRUCTURE,
        "career": CAREER_STRUCTURE,
    }.get(spread_type, MULTI_CARD_STRUCTURE)

    return f"""
Тип расклада: {spread_type}
Тема: {topic}

Вопрос пользователя:
{user_question}

Карты, позиции и символические значения:
{cards_text}

Фокус расклада:
{spread_instruction}

Рабочая задача:
- Найдите центральный рисунок сочетания и свяжите его с точным вопросом.
- Учитывайте функции позиций и влияние всех карт на общий вывод.
- Не добавляйте обстоятельства, которых нет в вопросе.
- Следуйте формату ниже и верните только готовый расклад.

Формат:
{output_structure}
""".strip()

def clean_reading_v3_answer(answer: str) -> str:
    """Remove only paired Markdown emphasis stars without rewriting text."""
    cleaned = re.sub(r"\*\*(?=\S)([^*\n]*?\S)\*\*", r"\1", answer)
    cleaned = re.sub(
        r"(?<!\*)\*(?=\S)([^*\n]*?\S)\*(?!\*)",
        r"\1",
        cleaned,
    )
    return cleaned


def inspect_reading_v3_answer(
    answer: str,
    spread_type: str,
    card_names: list[str] | None = None,
) -> dict[str, Any]:
    """Report format deviations without changing or regenerating the answer."""
    words = len(
        re.findall(
            r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?",
            answer,
        )
    )
    paragraphs = [part for part in re.split(r"\n\s*\n", answer) if part.strip()]
    min_words, max_words = (
        (90, 130)
        if spread_type == "daily_card"
        else ((110, 145) if spread_type == "love" else (130, 170))
    )
    issues: list[str] = []
    if not min_words <= words <= max_words:
        issues.append(f"word_count:{words}")
    expected_paragraphs = 3
    if len(paragraphs) != expected_paragraphs:
        issues.append(f"paragraph_count:{len(paragraphs)}")
    if re.search(r"\b(?:ты|твой|твоя|твои|тебе|тебя)\b", answer, re.IGNORECASE):
        issues.append("informal_address")
    named_cards = []
    if card_names:
        named_cards = [
            name for name in card_names
            if re.search(rf"(?<!\\w){re.escape(name)}(?!\\w)", answer, re.IGNORECASE)
        ]
    if (
        spread_type == "love"
        and card_names
        and len(named_cards) < min(3, len(card_names))
    ):
        issues.append(f"named_cards:{len(named_cards)}")
    return {
        "word_count": words,
        "paragraph_count": len(paragraphs),
        "within_word_target": min_words <= words <= max_words,
        "has_expected_paragraphs": len(paragraphs) == expected_paragraphs,
        "named_card_count": len(named_cards),
        "issues": issues,
    }


def generate_reading_v3(
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    ai_call: Callable[[str], str | None],
    topic: str = "general",
) -> str:
    """Make exactly one AI call and apply non-generative local cleanup."""
    prompt = build_reading_v3_prompt(
        spread_type=spread_type,
        user_question=user_question,
        cards=cards,
        topic=topic,
    )
    answer = ai_call(prompt)
    if not answer:
        return ""
    return clean_reading_v3_answer(answer)
