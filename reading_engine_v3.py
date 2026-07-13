"""Experimental one-call Reading Engine v3 for Moon Mentor.

The module is isolated from main.py and Reading Engine v2. It builds a compact
prompt, makes exactly one AI call, and only removes Markdown emphasis markers
from the returned text.
"""

import re
from typing import Any, Callable


SPREAD_POSITIONS = {
    "love": (
        "Что видно в контакте",
        "Центральное напряжение",
        "Практический ориентир",
    ),
    "career": (
        "Возможность",
        "Неясность или риск",
        "Условие решения",
    ),
    "personal_question": (
        "Центр вопроса",
        "Что важно увидеть",
        "На что опереться",
    ),
}


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
    """Build the short production prompt for a single AI request."""
    cards_text = format_cards_v3(prepare_cards_v3(cards, spread_type, topic))

    return f"""
Ты — Moon Mentor. Создай цельный символический разбор Таро на русском языке.

Вопрос пользователя:
{user_question}

Тип расклада:
{spread_type}

Карты и позиции:
{cards_text}

Требования к ответу:
- Объём строго 180–220 слов. Перед выдачей молча проверь объём. Если слов меньше 180, углуби центральную дилемму или критерий проверки без повторов; подсчёт не показывай.
- Начни с прямого ответа на вопрос, без вступления и пересказа вопроса; если фактов недостаточно для однозначного вывода, сформулируй ответ условно.
- Выдели одну центральную дилемму, которую показывает сочетание карт.
- Свяжи карты в одну линию рассуждения. Не создавай отдельный абзац или мини-толкование для каждой карты.
- Не перечисляй карты по очереди и не повторяй их словарные значения.
- Назови один наблюдаемый критерий: что пользователь может проверить в реальных действиях, словах или условиях. Не описывай будущий результат так, будто он обязательно наступит.
- Заверши одним конкретным следующим шагом, который не требует подстраиваться под выдуманные потребности другого человека.
- Фактами считай только сведения из вопроса пользователя. Даже тепло, дистанцию и неясность называй фактами только со ссылкой на описание пользователя.
- Карты используй как символический ракурс, а не как доказательство событий, чувств, качеств характера или мотивов.
- Пауза и дистанция — только наблюдаемые действия. Не объясняй их потребностью в пространстве, страхом, неготовностью, внутренним ритмом, желанием побыть одному или другими скрытыми причинами.
- Не утверждай, что знаешь мысли, чувства, намерения, склонности или готовность другого человека.
- Не пиши «карта подтверждает», «действительно означает», «это не отторжение», «скрытые детали» и подобные утверждения о неизвестных фактах.
- Не предсказывай, что человек вернётся, проявится или поступит определённым образом.
- Не используй Markdown-звёздочки.
- Пиши тепло, ясно и без эзотерического пафоса.
- Верни только готовый расклад.
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
