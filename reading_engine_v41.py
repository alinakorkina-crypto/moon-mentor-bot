"""One-call Reading Engine v4.1: validated analysis plus complete final prose."""

import json
import re
from typing import Any, Callable

from reading_engine_v4 import (
    SPREAD_POSITIONS_V4,
    build_local_fallback_v4,
    prepare_cards_v4,
)


V41_SYSTEM_INSTRUCTION = """
Вы — редактор Moon Mentor. Таро используется только как символический язык для
размышления, а не как предсказание или чтение чужих мыслей.

Верните строго JSON по заданной схеме.

Сначала отделите известные факты от символического прочтения:
- facts_used: только короткие точные цитаты из вопроса пользователя;
- unknowns_kept_open: что нельзя установить из вопроса и карт;
- card_roles: по одной краткой символической функции для каждой карты.

Затем напишите final_text — готовый ответ пользователю:
- ровно 3 коротких абзаца, ориентир 110–150 слов;
- первый абзац прямо отвечает на вопрос, но не принимает решение за человека;
- второй создаёт единый рисунок расклада: называет все карты и показывает их
  противоречие, усиление или переход, а не перечисляет значения;
- третий даёт один конкретный критерий ясности и завершается одним точным
  нейтральным вопросом для размышления;
- текст должен звучать тепло, легко и естественно на русском языке;
- не добавляйте приветствие, заголовки, списки и Markdown;
- не используйте канцелярские и тяжёлые обороты: «нецелесообразно»,
  «для вашего благополучия», «ненасильственная мера», «олицетворяет»,
  «символизируемый», «данная ситуация», «правила игры»;
- не угадывайте мысли, чувства, мотивы или намерения другого человека;
- не придумывайте скрытые причины, не обещайте исход и не давайте директивных
  советов «соглашайтесь», «откажитесь», «продолжайте», «прекратите»;
- не превращайте ответ в отказ от интерпретации и не повторяйте вопрос пользователя.

Особенности темы:
- отношения: описывайте рисунок контакта и взаимность, не объясняя другого человека;
- карьера: сопоставляйте привлекательность возможности с известными условиями роли;
- общий вопрос: найдите главное напряжение и опору для личного выбора;
- карта дня: покажите один полезный ракурс дня без прогноза;
- полный расклад: выделите центральный мотив, не разбирая карты по очереди.
""".strip()


V41_RESPONSE_SCHEMA = {
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
        "final_text": {"type": "string"},
    },
    "required": ["facts_used", "unknowns_kept_open", "card_roles", "final_text"],
}


HIGH_RISK_PATTERNS_V41 = (
    r"\b(?:он|она)\s+(?:хочет|боится|чувствует|думает|выбирает|нуждается|планирует)",
    r"\b(?:вам|тебе)\s+(?:нужно|необходимо|следует|стоит)\b",
    r"\b(?:продолжайте|прекратите|соглашайтесь|откажитесь)\b",
    r"\b(?:неизбеж\w*|гарантир\w*|скрыт\w*|хаос\w*)\b",
)

HEAVY_STYLE_PATTERNS_V41 = (
    r"\bнецелесообразн\w*\b",
    r"\bдля вашего благополучия\b",
    r"\bненасильственн\w*\b",
    r"\bолицетвор\w*\b",
    r"\bсимволизируем\w*\b",
    r"\bданн(?:ая|ой|ую) ситуаци\w*\b",
    r"\bправил\w* игр\w*\b",
)


def build_reading_v41_prompt(
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

Карты, позиции и допустимые символические значения:
{cards_text}

Сформируйте внутреннюю проверяемую основу и готовый final_text.
Используйте в final_text все карты, но не разбирайте их механически по одной.
Верните только JSON.
""".strip()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def clean_final_text_v41(text: str) -> str:
    cleaned = re.sub(r"\*\*(?=\S)([^*\n]*?\S)\*\*", r"\1", text)
    return re.sub(
        r"(?<!\*)\*(?=\S)([^*\n]*?\S)\*(?!\*)",
        r"\1",
        cleaned,
    ).strip()


def count_words_v41(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?", text))


def parse_v41_payload(raw_answer: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(raw_answer)
    except (json.JSONDecodeError, TypeError):
        return None, ["invalid_json"]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    return payload, []


def validate_v41_payload(
    payload: dict[str, Any],
    *,
    user_question: str,
    cards: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    final_text = payload.get("final_text")
    if not isinstance(final_text, str) or not final_text.strip():
        issues.append("missing:final_text")
        final_text = ""

    facts = payload.get("facts_used")
    if not isinstance(facts, list) or not facts:
        issues.append("missing:facts_used")
    else:
        question = _normalize(user_question)
        if any(
            not isinstance(fact, str)
            or not fact.strip()
            or _normalize(fact) not in question
            for fact in facts
        ):
            issues.append("unsupported_fact")

    unknowns = payload.get("unknowns_kept_open")
    if not isinstance(unknowns, list) or not unknowns:
        issues.append("missing:unknowns_kept_open")

    expected_names = [card["name"] for card in cards]
    roles = payload.get("card_roles")
    if not isinstance(roles, list):
        issues.append("missing:card_roles")
    else:
        role_names = [
            item.get("card")
            for item in roles
            if isinstance(item, dict) and isinstance(item.get("card"), str)
        ]
        if len(role_names) != len(expected_names) or set(role_names) != set(expected_names):
            issues.append("card_roles_mismatch")
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("role"), str)
            or not item["role"].strip()
            for item in roles
        ):
            issues.append("invalid_card_role")

    if final_text:
        paragraphs = [part.strip() for part in final_text.split("\n\n") if part.strip()]
        if len(paragraphs) != 3:
            issues.append("paragraph_count")
        words = count_words_v41(final_text)
        if words < 100 or words > 170:
            issues.append(f"word_count:{words}")
        if not final_text.rstrip().endswith("?"):
            issues.append("missing_final_question")
        if re.match(r"\s*(?:привет|приветствую|здравствуйте)\b", final_text, re.I):
            issues.append("greeting")
        missing = [
            name
            for name in expected_names
            if not re.search(rf"(?<!\w){re.escape(name)}(?!\w)", final_text, re.I)
        ]
        if missing:
            issues.append("final_text_missing_cards")
        if any(re.search(pattern, final_text, re.I) for pattern in HIGH_RISK_PATTERNS_V41):
            issues.append("high_risk_claim")
        if any(re.search(pattern, final_text, re.I) for pattern in HEAVY_STYLE_PATTERNS_V41):
            issues.append("heavy_style")

    return list(dict.fromkeys(issues))


def generate_reading_v41(
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
            validate_v41_payload(payload, user_question=user_question, cards=cards)
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
