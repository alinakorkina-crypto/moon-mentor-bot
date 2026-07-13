"""Reading Engine v4.2: v4.1 with Russian card-name morphology."""

import json
import re
from typing import Any, Callable

from reading_engine_v4 import build_local_fallback_v4
from reading_engine_v41 import (
    V41_RESPONSE_SCHEMA,
    V41_SYSTEM_INSTRUCTION,
    build_reading_v41_prompt,
    clean_final_text_v41,
    parse_v41_payload,
    validate_v41_payload,
)


V42_RESPONSE_SCHEMA = V41_RESPONSE_SCHEMA
V42_SYSTEM_INSTRUCTION = V41_SYSTEM_INSTRUCTION


def _word_form_pattern(word: str) -> str:
    """Return a conservative pattern for common Russian case forms."""
    escaped = re.escape(word)
    lower = word.lower()
    endings = (
        ("ая", ("ая", "ой", "ую", "ою")),
        ("яя", ("яя", "ей", "юю", "ею")),
        ("ый", ("ый", "ого", "ому", "ым", "ом")),
        ("ий", ("ий", "его", "ему", "им", "ем")),
        ("ое", ("ое", "ого", "ому", "ым", "ом")),
        ("ее", ("ее", "его", "ему", "им", "ем")),
        ("а", ("а", "ы", "е", "у", "ой", "ою")),
        ("я", ("я", "и", "е", "ю", "ей", "ею")),
        ("ь", ("ь", "и", "ью")),
        ("е", ("е", "я", "а", "ю", "у", "ем", "ом")),
        ("о", ("о", "а", "у", "ом", "е")),
        ("й", ("й", "я", "ю", "ем", "е")),
    )
    for ending, forms in endings:
        if lower.endswith(ending) and len(word) > len(ending) + 1:
            stem = re.escape(word[: -len(ending)])
            return stem + "(?:" + "|".join(forms) + ")"
    if lower[-1:].isalpha():
        return escaped + "(?:а|у|ом|е|ы|ов|ам|ами|ах)?"
    return escaped


def card_name_pattern_v42(name: str) -> str:
    """Build a whole-name matcher while allowing each word to decline."""
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", name)
    body = r"[\s–—-]+".join(_word_form_pattern(word) for word in words)
    return rf"(?<!\w){body}(?!\w)"


def missing_card_names_v42(text: str, cards: list[dict[str, Any]]) -> list[str]:
    return [
        card["name"]
        for card in cards
        if not re.search(card_name_pattern_v42(card["name"]), text, re.IGNORECASE)
    ]


def validate_v42_payload(
    payload: dict[str, Any],
    *,
    user_question: str,
    cards: list[dict[str, Any]],
) -> list[str]:
    issues = validate_v41_payload(
        payload,
        user_question=user_question,
        cards=cards,
    )
    issues = [issue for issue in issues if issue != "final_text_missing_cards"]
    final_text = payload.get("final_text")
    if isinstance(final_text, str) and final_text.strip():
        missing = missing_card_names_v42(final_text, cards)
        if missing:
            issues.append("missing_cards:" + "|".join(missing))
    return list(dict.fromkeys(issues))


def generate_reading_v42(
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    ai_call: Callable[[str], str | None],
    topic: str = "general",
) -> dict[str, Any]:
    prompt = build_reading_v41_prompt(spread_type, user_question, cards, topic)
    raw_answer = ai_call(prompt)
    if not raw_answer:
        return {
            "text": build_local_fallback_v4(
                spread_type=spread_type,
                user_question=user_question,
                cards=cards,
                topic=topic,
            ),
            "used_fallback": True,
            "issues": ["empty_ai_answer"],
        }

    payload, issues = parse_v41_payload(raw_answer)
    if payload is not None:
        issues.extend(
            validate_v42_payload(payload, user_question=user_question, cards=cards)
        )
    if payload is None or issues:
        return {
            "text": build_local_fallback_v4(
                spread_type=spread_type,
                user_question=user_question,
                cards=cards,
                topic=topic,
            ),
            "used_fallback": True,
            "issues": list(dict.fromkeys(issues)),
        }
    return {
        "text": clean_final_text_v41(payload["final_text"]),
        "used_fallback": False,
        "issues": [],
    }
