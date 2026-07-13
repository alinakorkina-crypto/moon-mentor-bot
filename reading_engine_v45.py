"""Reading Engine v4.5: choose the best of two texts from one AI request."""

import json
import re
from typing import Any, Callable

from reading_engine_v4 import build_local_fallback_v4, prepare_cards_v4
from reading_engine_v41 import clean_final_text_v41, count_words_v41
from reading_engine_v44 import validate_v44_payload


V45_SYSTEM_INSTRUCTION = """
Вы — редактор Moon Mentor. Таро используется как символический язык для
размышления, а не для предсказания или чтения чужих мыслей.

Верните строго JSON по схеме. Сначала заполните:
- facts_used — только короткие точные цитаты из вопроса;
- unknowns_kept_open — что нельзя установить из вопроса и карт;
- card_roles — каждая карта и её символическая функция.

Затем создайте два самостоятельных варианта final_text. Оба должны:
- состоять ровно из 3 коротких абзацев и содержать 110–150 слов;
- прямо отвечать на вопрос через условие выбора, не решая за пользователя;
- связывать все карты в один рисунок, а не пересказывать по очереди;
- отделять известные факты от символических версий;
- давать один наблюдаемый критерий и завершаться одним точным вопросом;
- звучать естественно, тепло и конкретно, без приветствия и Markdown;
- не угадывать мысли, чувства, мотивы или намерения другого человека;
- не давать директивных советов и не обещать исход.

Вариант 1 сделайте ясным и аналитичным. Вариант 2 — чуть теплее и образнее, но
без эзотерического пафоса. Не повторяйте формулировки между вариантами.

Для отношений описывайте рисунок контакта, а не партнёра. Не объясняйте причины
пауз. Критерием может быть взаимная инициатива или устойчивость связи. Не
повторяйте «решать только вам» и не предлагайте терпеть или принять неудобный
формат.

Ориентир хорошего тона:
«Здесь важны две стороны одной связи: то, что происходит в моменты близости, и
то, что остаётся между ними. Карты не объясняют другого человека, а помогают
сопоставить качество общения с его устойчивостью».

Для карьеры сопоставляйте привлекательность возможности с конкретностью условий:
обязанностями, полномочиями, подчинением и критериями результата.
""".strip()


V45_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "facts_used": {"type": "array", "items": {"type": "string"}},
        "unknowns_kept_open": {"type": "array", "items": {"type": "string"}},
        "card_roles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "card": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["card", "role"],
            },
        },
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"final_text": {"type": "string"}},
                "required": ["final_text"],
            },
        },
    },
    "required": ["facts_used", "unknowns_kept_open", "card_roles", "variants"],
}


SOFT_ISSUE_PREFIXES = (
    "heavy_style:",
    "love_style:",
    "love_psychologizing",
)

STYLE_PENALTIES = (
    (r"\bтолько вы\b", 14, "meta_only_you"),
    (r"\bникто не может\b", 14, "meta_nobody_can"),
    (r"\bреш(?:ать|ить) за вас\b", 12, "meta_decide_for_you"),
    (r"\bпредел\w* терпени\w*\b", 16, "dramatic_patience"),
    (r"\bжизнеспособност\w*\b", 8, "bureaucratic_viability"),
    (r"\bвнутренн\w* баланс\w*\b", 10, "generic_inner_balance"),
    (r"\bинвестир\w* (?:все )?(?:свои )?ожидан\w*\b", 12, "artificial_invest"),
    (r"\bправил\w* игр\w*\b", 10, "cliche_rules_game"),
    (r"\bважно\b", 3, "prescriptive_important"),
)


def build_reading_v45_prompt(
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    topic: str = "general",
) -> str:
    prepared = prepare_cards_v4(cards, spread_type, topic)
    cards_text = "\n".join(
        f"- {item['position']}: {item['name']} — {item['meaning']}"
        for item in prepared
    )
    return f"""
Тип расклада: {spread_type}
Тема: {topic}

Вопрос пользователя:
{user_question}

Карты, позиции и допустимые значения:
{cards_text}

Подготовьте общую проверяемую основу и два разных варианта готового ответа.
Верните только JSON.
""".strip()


def parse_v45_payload(raw_answer: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(raw_answer)
    except (json.JSONDecodeError, TypeError):
        return None, ["invalid_json"]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    return payload, []


def _variant_payload(payload: dict[str, Any], final_text: str) -> dict[str, Any]:
    return {
        "facts_used": payload.get("facts_used"),
        "unknowns_kept_open": payload.get("unknowns_kept_open"),
        "card_roles": payload.get("card_roles"),
        "final_text": final_text,
    }


def score_variant_v45(
    text: str,
    validation_issues: list[str],
) -> tuple[int, list[str]]:
    score = 100
    warnings = [
        issue for issue in validation_issues
        if issue.startswith(SOFT_ISSUE_PREFIXES)
    ]
    for warning in warnings:
        score -= 18 if warning == "love_psychologizing" else 12

    for pattern, penalty, label in STYLE_PENALTIES:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            score -= penalty * len(matches)
            warnings.append(label)

    card_listing = len(
        re.findall(
            r"\b(?:карта\s+)?[А-ЯЁ][а-яё]+\s+"
            r"(?:показывает|символизирует|предлагает|указывает)",
            text,
        )
    )
    if card_listing >= 2:
        score -= 6 * card_listing
        warnings.append("mechanical_card_listing")

    words = count_words_v41(text)
    score -= abs(words - 130) // 8
    return score, list(dict.fromkeys(warnings))


def evaluate_variants_v45(
    payload: dict[str, Any],
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    variants = payload.get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        return None, ["missing_two_variants"]

    evaluated = []
    rejection_issues: list[str] = []
    for index, variant in enumerate(variants[:2], start=1):
        if not isinstance(variant, dict) or not isinstance(variant.get("final_text"), str):
            rejection_issues.append(f"variant_{index}:missing_final_text")
            continue
        text = variant["final_text"].strip()
        issues = validate_v44_payload(
            _variant_payload(payload, text),
            spread_type=spread_type,
            user_question=user_question,
            cards=cards,
        )
        hard = [
            issue for issue in issues
            if not issue.startswith(SOFT_ISSUE_PREFIXES)
        ]
        if hard:
            rejection_issues.extend(f"variant_{index}:{issue}" for issue in hard)
            continue
        score, warnings = score_variant_v45(text, issues)
        evaluated.append(
            {
                "index": index,
                "text": text,
                "score": score,
                "warnings": warnings,
            }
        )

    if not evaluated:
        return None, rejection_issues or ["no_valid_variant"]
    return max(evaluated, key=lambda item: item["score"]), rejection_issues


def generate_reading_v45(
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    ai_call: Callable[[str], str | None],
    topic: str = "general",
) -> dict[str, Any]:
    prompt = build_reading_v45_prompt(spread_type, user_question, cards, topic)
    raw_answer = ai_call(prompt)
    if not raw_answer:
        return {
            "text": build_local_fallback_v4(
                spread_type=spread_type, user_question=user_question,
                cards=cards, topic=topic,
            ),
            "used_fallback": True, "issues": ["empty_ai_answer"],
            "selected_variant": None, "score": None, "warnings": [],
        }
    payload, issues = parse_v45_payload(raw_answer)
    selected = None
    if payload is not None:
        selected, evaluation_issues = evaluate_variants_v45(
            payload, spread_type=spread_type,
            user_question=user_question, cards=cards,
        )
        issues.extend(evaluation_issues)
    if selected is None:
        return {
            "text": build_local_fallback_v4(
                spread_type=spread_type, user_question=user_question,
                cards=cards, topic=topic,
            ),
            "used_fallback": True, "issues": list(dict.fromkeys(issues)),
            "selected_variant": None, "score": None, "warnings": [],
        }
    return {
        "text": clean_final_text_v41(selected["text"]),
        "used_fallback": False,
        "issues": [],
        "selected_variant": selected["index"],
        "score": selected["score"],
        "warnings": selected["warnings"],
    }
