"""Structured one-call Reading Engine v4 experiment for Moon Mentor.

The model returns evidence and prose components as JSON. Python validates the
structure before rendering three paragraphs. Invalid payloads use a local
fallback and never trigger a second AI request.
"""

import json
import re
from typing import Any, Callable


SPREAD_POSITIONS_V4 = {
    "daily_card": ("Фокус дня",),
    "love": (
        "Что непосредственно видно в контакте",
        "Что нарушает устойчивость или создаёт вопрос",
        "Какой ракурс помогает определить свою позицию",
    ),
    "career": (
        "Что привлекает внимание",
        "Какой информации или ясности не хватает",
        "Какая структура помогает оценить ситуацию",
    ),
    "personal_question": (
        "Центр вопроса",
        "Что усложняет понимание",
        "На что можно опереться",
    ),
    "full": (
        "Центральная тема",
        "Что осложняет ситуацию",
        "Что поддерживает",
        "Куда направить внимание",
    ),
}


V4_SYSTEM_INSTRUCTION = """
Вы — аналитический редактор Moon Mentor. Таро здесь используется только как
символический язык для размышления.

Верните строго JSON по заданной схеме. Не создавайте финальный расклад целиком.

Правила:
- facts_used: только короткие точные цитаты из вопроса пользователя.
- unknowns_kept_open: обстоятельства, которые нельзя установить из вопроса и карт.
- card_roles: по одной символической функции для каждой карты; функция карты — символическая версия и не является фактом о человеке или ситуации.
- direct_response: прямой ответ по существу через условие выбора, без решения за
  пользователя и без новых обстоятельств.
- synthesis: одна связная мысль, в которой названы все карты и показано, как они
  влияют друг на друга. Не перечисляйте их значения по очереди.
- clarity_basis: один наблюдаемый факт, вопрос к реальности или недостающая
  информация; не команда пользователю.
- reflection_question: один нейтральный вопрос, не склоняющий к варианту решения.
- Не угадывайте мысли, чувства, мотивы и намерения людей.
- Не предсказывайте исход, не драматизируйте неопределённость и не нормализуйте
  неудобную ситуацию как формат, к которому пользователь должен приспособиться.
- Пишите на «вы», ясно и естественно, без приветствия и Markdown.
""".strip()


V4_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "direct_response": {"type": "string"},
        "facts_used": {
            "type": "array",
            "items": {"type": "string"},
        },
        "unknowns_kept_open": {
            "type": "array",
            "items": {"type": "string"},
        },
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
        "synthesis": {"type": "string"},
        "clarity_basis": {"type": "string"},
        "reflection_question": {"type": "string"},
    },
    "required": [
        "direct_response",
        "facts_used",
        "unknowns_kept_open",
        "card_roles",
        "synthesis",
        "clarity_basis",
        "reflection_question",
    ],
}


HIGH_RISK_PATTERNS = (
    r"\b(?:он|она)\s+(?:хочет|боится|чувствует|думает|выбирает|нуждается|планирует)",
    r"\b(?:вам|тебе)\s+(?:нужно|необходимо|следует|стоит)\b",
    r"\b(?:продолжайте|прекратите|соглашайтесь|откажитесь)\b",
    r"\bнеизбеж\w*\b",
    r"\bгарантир\w*\b",
    r"\bискренн(?:ий|яя|ее|ие|его|ему|им|ую|ой|о)\b",
    r"\bскрыт(?:ый|ая|ое|ые|ых|ыми|ую|ой)\b",
    r"\bредк\w*\s+встреч\w*\b",
    r"\bбез обязательств\b",
    r"\b(?:хаос|хаотичн\w*)\b",
)


def prepare_cards_v4(
    cards: list[dict[str, Any]],
    spread_type: str,
    topic: str = "general",
) -> list[dict[str, str]]:
    positions = SPREAD_POSITIONS_V4.get(
        spread_type,
        SPREAD_POSITIONS_V4["personal_question"],
    )
    prepared = []
    for index, card in enumerate(cards):
        meaning = card.get(topic, card.get("general", ""))
        prepared.append(
            {
                "position": (
                    positions[index]
                    if index < len(positions)
                    else f"Дополнительный ракурс {index + 1}"
                ),
                "name": card["name"],
                "meaning": meaning,
            }
        )
    return prepared


def build_reading_v4_prompt(
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    topic: str = "general",
) -> str:
    prepared = prepare_cards_v4(cards, spread_type, topic)
    cards_text = "\n".join(
        f"- {item['position']}: {item['name']} — символическая тема: {item['meaning']}"
        for item in prepared
    )
    return f"""
Тип расклада: {spread_type}
Тема: {topic}

Вопрос пользователя:
{user_question}

Карты и позиции:
{cards_text}

Сформируйте структурированный материал для трёх коротких абзацев.
В direct_response ответьте на точный вопрос через ключевое условие выбора.
В synthesis свяжите все карты в одну мысль.
Верните только JSON.
""".strip()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _clean_component(text: str) -> str:
    cleaned = re.sub(r"\*\*(?=\S)([^*\n]*?\S)\*\*", r"\1", text)
    return re.sub(r"(?<!\*)\*(?=\S)([^*\n]*?\S)\*(?!\*)", r"\1", cleaned).strip()


def parse_v4_payload(raw_answer: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(raw_answer)
    except (json.JSONDecodeError, TypeError):
        return None, ["invalid_json"]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    return payload, []


def validate_v4_payload(
    payload: dict[str, Any],
    *,
    user_question: str,
    cards: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    required_strings = (
        "direct_response",
        "synthesis",
        "clarity_basis",
        "reflection_question",
    )
    for key in required_strings:
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            issues.append(f"missing:{key}")

    facts = payload.get("facts_used")
    if not isinstance(facts, list) or not facts:
        issues.append("missing:facts_used")
    else:
        normalized_question = _normalize(user_question)
        for fact in facts:
            if (
                not isinstance(fact, str)
                or not fact.strip()
                or _normalize(fact) not in normalized_question
            ):
                issues.append("unsupported_fact")
                break

    unknowns = payload.get("unknowns_kept_open")
    if not isinstance(unknowns, list) or not unknowns:
        issues.append("missing:unknowns_kept_open")

    roles = payload.get("card_roles")
    expected_names = [card["name"] for card in cards]
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
        for item in roles:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("role"), str)
                or not item["role"].strip()
            ):
                issues.append("invalid_card_role")
                break

    synthesis = payload.get("synthesis", "")
    if isinstance(synthesis, str):
        missing_names = [
            name
            for name in expected_names
            if not re.search(
                rf"(?<!\w){re.escape(name)}(?!\w)",
                synthesis,
                flags=re.IGNORECASE,
            )
        ]
        if missing_names:
            issues.append("synthesis_missing_cards")

    question = payload.get("reflection_question", "")
    if isinstance(question, str) and question.strip() and not question.rstrip().endswith("?"):
        issues.append("reflection_not_question")

    prose = " ".join(
        str(payload.get(key, ""))
        for key in (
            "direct_response",
            "synthesis",
            "clarity_basis",
            "reflection_question",
        )
    )
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, prose, flags=re.IGNORECASE):
            issues.append("high_risk_claim")
            break

    if re.match(r"\s*(?:привет|приветствую|здравствуйте)\b", prose, re.IGNORECASE):
        issues.append("greeting")

    return list(dict.fromkeys(issues))


def render_v4_payload(payload: dict[str, Any]) -> str:
    paragraph_one = _clean_component(payload["direct_response"])
    paragraph_two = _clean_component(payload["synthesis"])
    clarity = _clean_component(payload["clarity_basis"])
    question = _clean_component(payload["reflection_question"])
    paragraph_three = f"{clarity} {question}".strip()
    return "\n\n".join((paragraph_one, paragraph_two, paragraph_three))


def build_local_fallback_v4(
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    topic: str = "general",
) -> str:
    prepared = prepare_cards_v4(cards, spread_type, topic)
    names = [item["name"] for item in prepared]

    if spread_type == "love":
        first = (
            "В этом вопросе решение зависит не только от теплоты общения, но и от того, "
            "насколько контакт сохраняет взаимность и устойчивость между его отдельными эпизодами."
        )
        if len(prepared) >= 3:
            second = (
                f"{names[0]} освещает заметную сторону контакта, {names[1]} добавляет "
                f"к ней тему дистанции, а {names[2]} переводит их сочетание в вопрос "
                "о подходящей вам мере участия. Вместе они описывают не причины чужого "
                "поведения, а контраст между качеством общения и его непрерывностью."
            )
        else:
            second = "Карты предлагают рассмотреть качество контакта отдельно от его устойчивости."
        third = (
            "Добавить ясности может наблюдение за тем, возникает ли инициатива поддерживать "
            "и возобновлять связь с обеих сторон. Какой формат контакта соответствует вашим "
            "потребностям в близости и регулярности?"
        )
    elif spread_type == "career":
        first = (
            "В этом вопросе выбор зависит от того, достаточно ли конкретно описана работа, "
            "которая стоит за более высокой зарплатой."
        )
        if len(prepared) >= 3:
            second = (
                f"{names[0]} вносит тему движения, {names[1]} показывает предел имеющейся "
                f"ясности, а {names[2]} связывает их через структуру роли. Общий рисунок "
                "переносит внимание с привлекательности предложения на возможность оценить "
                "его реальные обязанности и ответственность."
            )
        else:
            second = "Карты сопоставляют привлекательность возможности с ясностью её условий."
        third = (
            "Для оценки предложения имеют значение обязанности, полномочия, подчинение и "
            "ожидаемые результаты. Какая информация о роли необходима вам, чтобы сравнить "
            "финансовое преимущество с содержанием будущей работы?"
        )
    else:
        first = (
            "Расклад не выбирает решение за вас, а показывает, от какого условия зависит "
            "более ясное понимание ситуации."
        )
        second = (
            "Символические темы карт образуют несколько ракурсов одного вопроса; их важно "
            "сверять только с обстоятельствами, которые вам действительно известны."
        )
        third = (
            "Добавить ясности может один проверяемый факт, которого сейчас не хватает. "
            "Что изменило бы ваше понимание этой ситуации?"
        )

    return "\n\n".join((first, second, third))


def generate_reading_v4(
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    ai_call: Callable[[str], str | None],
    topic: str = "general",
) -> dict[str, Any]:
    prompt = build_reading_v4_prompt(spread_type, user_question, cards, topic)
    raw_answer = ai_call(prompt)
    if not raw_answer:
        issues = ["empty_ai_answer"]
        return {
            "text": build_local_fallback_v4(
                spread_type=spread_type,
                user_question=user_question,
                cards=cards,
                topic=topic,
            ),
            "used_fallback": True,
            "issues": issues,
        }

    payload, parse_issues = parse_v4_payload(raw_answer)
    issues = list(parse_issues)
    if payload is not None:
        issues.extend(
            validate_v4_payload(
                payload,
                user_question=user_question,
                cards=cards,
            )
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
        "text": render_v4_payload(payload),
        "used_fallback": False,
        "issues": [],
    }
