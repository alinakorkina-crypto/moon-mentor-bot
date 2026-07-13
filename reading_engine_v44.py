"""Reading Engine v4.4: separate editorial profiles by spread type."""

import re
from typing import Any, Callable

from reading_engine_v4 import build_local_fallback_v4
from reading_engine_v41 import (
    HEAVY_STYLE_PATTERNS_V41,
    V41_RESPONSE_SCHEMA,
    build_reading_v41_prompt,
    clean_final_text_v41,
    parse_v41_payload,
)
from reading_engine_v42 import V42_SYSTEM_INSTRUCTION
from reading_engine_v43 import validate_v43_payload


V44_RESPONSE_SCHEMA = V41_RESPONSE_SCHEMA
V44_DEFAULT_SYSTEM_INSTRUCTION = V42_SYSTEM_INSTRUCTION
V44_LOVE_SYSTEM_INSTRUCTION = """
Вы — редактор Moon Mentor. Таро здесь используется как символический язык для
размышления, а не для предсказания или чтения мыслей другого человека.

Верните строго JSON: facts_used, unknowns_kept_open, card_roles и final_text.
facts_used содержит только короткие точные цитаты из вопроса.
unknowns_kept_open сохраняет неизвестными причины, мотивы и чувства другого человека.
card_roles содержит каждую карту и её краткую символическую функцию.

final_text — готовый ответ пользователю из ровно 3 коротких абзацев, 110–150 слов:
1. Прямо покажите, от какого личного условия зависит решение пользователя. Не
   добавляйте последствий, которых нет в вопросе, и не решайте за человека.
2. Назовите все карты и свяжите их в один рисунок контакта. Карты описывают ситуацию,
   а не партнёра. Не превращайте карту в человека, который уходит,
   боится, хочет или держит дистанцию.
3. Назовите один наблюдаемый критерий — взаимную инициативу или устойчивость
   связи — и завершите одним вопросом о желаемом формате контакта.

Пишите легко и конкретно. Не объясняйте причины чужого поведения. Не советуйте
принять существующий формат или приспособиться к нему. Не добавляйте «искренний
свет», «холод», «нагрев», «внутренний баланс», «инвестировать ожидания»,
«повседневная жизнь», «пространство для других интересов», «тревога»,
«опустошение», «чувствовать себя ценной». Не пишите «карта предлагает» или
«важно опираться». Не используйте приветствие, заголовки, списки или Markdown.
""".strip()


LOVE_V44_STYLE_PATTERNS = (
    r"\bвнутренн\w* баланс\w*\b",
    r"\bинвестир\w* (?:все )?(?:свои )?ожидан\w*\b",
    r"\bповседневн\w* жизн\w*\b",
    r"\bпространств\w* для других интерес\w*\b",
    r"\bне наруша\w* вашу\b",
    r"\bкарт\w* предлага\w*\b",
    r"\bважно опираться\b",
)


def build_reading_v44_prompt(
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    topic: str = "general",
) -> str:
    return build_reading_v41_prompt(spread_type, user_question, cards, topic)


def _matched_phrase(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "_", match.group(0).strip().lower())
    return None


def validate_v44_payload(
    payload: dict[str, Any],
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
) -> list[str]:
    issues = validate_v43_payload(
        payload,
        spread_type=spread_type,
        user_question=user_question,
        cards=cards,
    )
    final_text = payload.get("final_text")
    if not isinstance(final_text, str):
        return issues

    if "heavy_style" in issues:
        issues = [issue for issue in issues if issue != "heavy_style"]
        phrase = _matched_phrase(final_text, HEAVY_STYLE_PATTERNS_V41)
        issues.append("heavy_style:" + (phrase or "unknown"))

    if spread_type == "love":
        phrase = _matched_phrase(final_text, LOVE_V44_STYLE_PATTERNS)
        if phrase:
            issues.append("love_style:" + phrase)

    return list(dict.fromkeys(issues))


def generate_reading_v44(
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    ai_call: Callable[[str], str | None],
    topic: str = "general",
) -> dict[str, Any]:
    prompt = build_reading_v44_prompt(spread_type, user_question, cards, topic)
    raw_answer = ai_call(prompt)
    if not raw_answer:
        return {
            "text": build_local_fallback_v4(
                spread_type=spread_type, user_question=user_question,
                cards=cards, topic=topic,
            ),
            "used_fallback": True,
            "issues": ["empty_ai_answer"],
        }
    payload, issues = parse_v41_payload(raw_answer)
    if payload is not None:
        issues.extend(
            validate_v44_payload(
                payload, spread_type=spread_type,
                user_question=user_question, cards=cards,
            )
        )
    if payload is None or issues:
        return {
            "text": build_local_fallback_v4(
                spread_type=spread_type, user_question=user_question,
                cards=cards, topic=topic,
            ),
            "used_fallback": True,
            "issues": list(dict.fromkeys(issues)),
        }
    return {
        "text": clean_final_text_v41(payload["final_text"]),
        "used_fallback": False,
        "issues": [],
    }
