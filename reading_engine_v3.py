"""Experimental one-call Reading Engine v3.2 for Moon Mentor.

The module is isolated from main.py and Reading Engine v2. It builds a compact
topic-aware prompt, makes exactly one AI call, and only removes Markdown
emphasis markers from the returned text.
"""

import re
from typing import Any, Callable


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
        "Описывайте только рисунок контакта, прямо названные пользователем действия, "
        "взаимность, инициативу, повторяемость и границы. Тёплый эпизод не равен "
        "устойчивой вовлечённости. Не советуйте ждать, терпеть исчезновения, принимать "
        "человека «таким, какой он есть», снижать ожидания или подстраиваться под его "
        "предполагаемый ритм. Критерий должен проверять, поддерживают ли контакт двое."
    ),
    "career": (
        "Анализируйте возможности, ограничения, условия, ответственность и проверяемые "
        "риски. Недостаток информации называйте недостатком информации, а не скрытой "
        "опасностью, тайной или препятствием. Не обещайте успех, рост или повышение."
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


MULTI_CARD_STRUCTURE = """
Напишите ровно четыре коротких абзаца без заголовков:
1. 35–45 слов: прямой ответ и центральная дилемма.
2. 80–95 слов: взаимодействие карт и роль их позиций; не пересказывайте карты по очереди.
3. 35–40 слов: один наблюдаемый критерий, который можно проверить в действиях, словах или условиях.
4. 30–40 слов: один конкретный следующий шаг и один точный вопрос для размышления.

Общий объём четырёх абзацев — строго 180–220 слов.
Перед выдачей молча проверьте объём каждого абзаца и всего ответа.
Не показывайте подсчёт и не добавляйте заголовки.
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
    """Build the compact topic-aware prompt for a single AI request."""
    cards_text = format_cards_v3(prepare_cards_v3(cards, spread_type, topic))
    spread_instruction = SPREAD_INSTRUCTIONS.get(
        spread_type,
        SPREAD_INSTRUCTIONS["personal_question"],
    )
    output_structure = (
        DAILY_STRUCTURE if spread_type == "daily_card" else MULTI_CARD_STRUCTURE
    )

    return f"""
Ты — Moon Mentor. Создай цельный символический разбор Таро на русском языке.

Тип расклада:
{spread_type}

Тема:
{topic}

Вопрос пользователя:
{user_question}

Единственные допустимые факты о ситуации:
{user_question}

Карты и позиции:
{cards_text}

Инструкция для этого типа расклада:
{spread_instruction}

Задача:
- Начни с прямого ответа на вопрос; если фактов недостаточно, сформулируй ответ условно.
- Выдели одну центральную тему и главное противоречие или усиление сочетания.
- Свяжи карты в одну линию. Не создавай отдельное толкование для каждой карты.
- Учитывай позиции карт. Значения карт — символические ракурсы, а не факты о ситуации.
- Добавь одну новую мысль, которой нет в формулировке вопроса.
- Назови один наблюдаемый критерий, а не предполагаемый будущий результат.
- Заверши одним конкретным следующим шагом и одним точным вопросом для размышления.
- Фактами считай только сведения из вопроса пользователя.
- Даже тепло, дистанцию и неясность называй фактами только со ссылкой на описание пользователя.
- Не объясняй паузу или дистанцию потребностью в пространстве, страхом, неготовностью,
  внутренним ритмом, характером, желанием побыть одному или другой скрытой причиной.
- Не утверждай, что знаешь мысли, чувства, намерения, склонности или готовность другого человека.
- Не пиши «карта подтверждает», «действительно означает», «это не отторжение»,
  «скрытые детали» и подобные утверждения о неизвестных фактах.
- Не предсказывай, что человек вернётся, проявится, изменится или поступит определённым образом.
- Не используй Markdown-звёздочки.
- Пиши тепло, ясно, конкретно и без эзотерического пафоса.
- Верни только готовый расклад.

Структура ответа:
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
