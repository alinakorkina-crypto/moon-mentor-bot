"""Two-pass Reading Engine v5 experiment for Moon Mentor personal questions.

Pass 1 builds a grounded interpretation as JSON. Pass 2 edits that interpretation
into a complete Telegram answer. Python validates both stages and never rewrites
the model's prose beyond removing Markdown stars.
"""

import json
import re
from typing import Any, Callable


PERSONAL_POSITIONS_V5 = (
    "Исходный импульс или возможность движения",
    "Главное препятствие, перелом или противоречие",
    "Что остаётся открытым и завершает общий рисунок",
)


ANALYSIS_SYSTEM_V5 = """
Вы — аналитик раскладов Moon Mentor. Таро используется как символический язык
для размышления, а не как достоверное предсказание и не как чтение чужих мыслей.

Верните строго JSON по заданной схеме. Не пишите финальный ответ пользователю.

Правила анализа:
- определите точный тип вопроса: инициатива, чувства, причины поведения, выбор
  пользователя или общий вопрос;
- facts_used содержит только короткие точные цитаты из вопроса;
- unknowns_kept_open сохраняет неизвестными мысли, чувства, мотивы, намерения,
  сроки и будущие действия другого человека;
- учтите позицию и допустимое символическое значение каждой карты;
- card_roles должен содержать все карты по одному разу;
- combination_synthesis связывает все карты в последовательный рисунок:
  импульс → препятствие или изменение → то, что остаётся;
- не позволяйте одной яркой карте отменить остальные;
- answer_tendency описывает только тенденцию символического рисунка:
  supportive, blocked, mixed или open;
- direct_answer_basis объясняет, почему выбран именно этот тип тенденции, но не
  утверждает будущий исход как факт;
- observable_criterion должен быть проверяемым в реальности;
- reflection_question — один нейтральный вопрос пользователю.
""".strip()


EDITOR_SYSTEM_V5 = """
Вы — старший редактор Moon Mentor. Получите вопрос, карты и проверенный
структурированный анализ. На его основе напишите один готовый ответ.

Верните строго JSON с полем final_text.

Требования к final_text:
- ровно 3 коротких абзаца, ориентир 110–150 слов;
- первый абзац прямо отвечает на вопрос через формулировку «по символике
  сочетания», «расклад скорее показывает» или «здесь нет уверенного указания»;
- не выдавайте ответ за достоверный прогноз и не повторяйте длинный дисклеймер;
- второй абзац называет все карты и показывает их взаимодействие в порядке
  позиций, а не пересказывает три значения по отдельности;
- третий абзац даёт один наблюдаемый критерий и заканчивается одним точным
  вопросом для размышления;
- не утверждайте, что другой человек думает, чувствует, хочет, боится, решил или
  обязательно совершит конкретное действие;
- не придумывайте прошлые события, скрытые причины и сроки;
- не давайте команд и не используйте «вам нужно», «вам следует», «важно»;
- пишите живо и легко, без приветствия, заголовков, списков, Markdown,
  канцелярита, эзотерического пафоса и психологических диагнозов.
""".strip()


ANALYSIS_SCHEMA_V5 = {
    "type": "object",
    "properties": {
        "question_mode": {"type": "string"},
        "facts_used": {"type": "array", "items": {"type": "string"}},
        "unknowns_kept_open": {"type": "array", "items": {"type": "string"}},
        "card_roles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "card": {"type": "string"},
                    "position": {"type": "string"},
                    "contribution": {"type": "string"},
                },
                "required": ["card", "position", "contribution"],
            },
        },
        "answer_tendency": {"type": "string"},
        "direct_answer_basis": {"type": "string"},
        "combination_synthesis": {"type": "string"},
        "observable_criterion": {"type": "string"},
        "reflection_question": {"type": "string"},
    },
    "required": [
        "question_mode",
        "facts_used",
        "unknowns_kept_open",
        "card_roles",
        "answer_tendency",
        "direct_answer_basis",
        "combination_synthesis",
        "observable_criterion",
        "reflection_question",
    ],
}


EDITOR_SCHEMA_V5 = {
    "type": "object",
    "properties": {"final_text": {"type": "string"}},
    "required": ["final_text"],
}


HIGH_RISK_PATTERNS_V5 = (
    r"\b(?:он|она|человек)\s+(?:точно\s+|обязательно\s+|скоро\s+)?"
    r"(?:не\s+)?(?:выйдет|напишет|позвонит|верн[её]тся|проявится)\b",
    r"\b(?:он|она)\s+(?:хочет|боится|чувствует|думает|решил[аи]?|планирует)\b",
    r"\b(?:вам|тебе)\s+(?:нужно|необходимо|следует|стоит)\b",
    r"\b(?:ждите|напишите|позвоните|прекратите|продолжайте)\b",
    r"\b(?:точно|обязательно|гарантированно)\s+(?:случится|произойд[её]т|будет)\b",
)


def prepare_cards_v5(cards: list[dict[str, Any]], topic: str = "general") -> list[dict[str, str]]:
    prepared = []
    for index, card in enumerate(cards):
        meaning = card.get(topic) or card.get("general") or ""
        position = (
            PERSONAL_POSITIONS_V5[index]
            if index < len(PERSONAL_POSITIONS_V5)
            else f"Дополнительный ракурс {index + 1}"
        )
        prepared.append(
            {"name": card["name"], "position": position, "meaning": meaning}
        )
    return prepared


def build_analysis_prompt_v5(
    user_question: str,
    cards: list[dict[str, Any]],
    topic: str = "general",
) -> str:
    prepared = prepare_cards_v5(cards, topic)
    card_block = "\n".join(
        f"- {item['position']}: {item['name']} — {item['meaning']}"
        for item in prepared
    )
    return f"""
Тип расклада: personal_question
Тема: {topic}

Вопрос пользователя:
{user_question}

Карты, позиции и допустимые символические значения:
{card_block}

Постройте проверяемый анализ сочетания и верните только JSON.
""".strip()


def build_editor_prompt_v5(
    user_question: str,
    cards: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> str:
    names = " — ".join(card["name"] for card in cards)
    analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
    return f"""
Вопрос пользователя:
{user_question}

Карты:
{names}

Проверенный анализ:
{analysis_json}

Напишите финальный ответ строго на основе анализа. Верните только JSON.
""".strip()


def parse_json_object_v5(raw: str | None) -> tuple[dict[str, Any] | None, list[str]]:
    if not raw:
        return None, ["empty_answer"]
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, ["invalid_json"]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    return payload, []


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().replace("ё", "е"))


def _word_form_pattern(word: str) -> str:
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
            return (
                re.escape(word[: -len(ending)])
                + "(?:"
                + "|".join(forms)
                + ")"
            )
    return escaped + "(?:а|у|ом|е|ы|ов|ам|ами|ах)?" if lower[-1:].isalpha() else escaped


def card_name_pattern_v5(name: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", name)
    body = r"[\s–—-]+".join(_word_form_pattern(word) for word in words)
    return rf"(?<!\w){body}(?!\w)"


def _missing_cards(text: str, cards: list[dict[str, Any]]) -> list[str]:
    return [
        card["name"]
        for card in cards
        if not re.search(card_name_pattern_v5(card["name"]), text, re.IGNORECASE)
    ]


def validate_analysis_v5(
    payload: dict[str, Any],
    *,
    user_question: str,
    cards: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    string_fields = (
        "question_mode",
        "answer_tendency",
        "direct_answer_basis",
        "combination_synthesis",
        "observable_criterion",
        "reflection_question",
    )
    for field in string_fields:
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            issues.append(f"missing:{field}")

    tendency = payload.get("answer_tendency")
    if tendency not in {"supportive", "blocked", "mixed", "open"}:
        issues.append("invalid_answer_tendency")

    facts = payload.get("facts_used")
    if not isinstance(facts, list) or not facts:
        issues.append("missing:facts_used")
    else:
        normalized_question = _normalize(user_question)
        if any(
            not isinstance(fact, str)
            or not fact.strip()
            or _normalize(fact) not in normalized_question
            for fact in facts
        ):
            issues.append("unsupported_fact")

    unknowns = payload.get("unknowns_kept_open")
    if not isinstance(unknowns, list) or not unknowns:
        issues.append("missing:unknowns_kept_open")

    roles = payload.get("card_roles")
    expected_names = [card["name"] for card in cards]
    if not isinstance(roles, list):
        issues.append("missing:card_roles")
    else:
        role_names = [
            role.get("card")
            for role in roles
            if isinstance(role, dict) and isinstance(role.get("card"), str)
        ]
        if len(role_names) != len(expected_names) or set(role_names) != set(expected_names):
            issues.append("card_roles_mismatch")
        expected_positions = PERSONAL_POSITIONS_V5[: len(cards)]
        role_positions = [
            role.get("position") for role in roles if isinstance(role, dict)
        ]
        if tuple(role_positions) != tuple(expected_positions):
            issues.append("card_positions_mismatch")
        if any(
            not isinstance(role, dict)
            or not isinstance(role.get("contribution"), str)
            or not role["contribution"].strip()
            for role in roles
        ):
            issues.append("invalid_card_role")

    synthesis = payload.get("combination_synthesis")
    if isinstance(synthesis, str):
        missing = _missing_cards(synthesis, cards)
        if missing:
            issues.append("analysis_missing_cards:" + "|".join(missing))

    reflection = payload.get("reflection_question")
    if isinstance(reflection, str) and reflection.strip() and not reflection.rstrip().endswith("?"):
        issues.append("reflection_not_question")

    return list(dict.fromkeys(issues))


def count_words_v5(text: str) -> int:
    return len(
        re.findall(
            r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?",
            text,
        )
    )


def validate_final_text_v5(
    payload: dict[str, Any],
    *,
    cards: list[dict[str, Any]],
) -> list[str]:
    final_text = payload.get("final_text")
    if not isinstance(final_text, str) or not final_text.strip():
        return ["missing:final_text"]

    issues: list[str] = []
    paragraphs = [part.strip() for part in final_text.split("\n\n") if part.strip()]
    if len(paragraphs) != 3:
        issues.append("paragraph_count")
    word_count = count_words_v5(final_text)
    if word_count < 100 or word_count > 170:
        issues.append(f"word_count:{word_count}")
    if not final_text.rstrip().endswith("?"):
        issues.append("missing_final_question")
    missing = _missing_cards(final_text, cards)
    if missing:
        issues.append("final_missing_cards:" + "|".join(missing))
    if re.match(r"\s*(?:привет|приветствую|здравствуйте)\b", final_text, re.IGNORECASE):
        issues.append("greeting")
    if any(re.search(pattern, final_text, re.IGNORECASE) for pattern in HIGH_RISK_PATTERNS_V5):
        issues.append("high_risk_claim")
    if re.search(r"\b(?:вселенн\w*|предначертан\w*|судьб\w*)\b", final_text, re.IGNORECASE):
        issues.append("esoteric_pafos")
    return list(dict.fromkeys(issues))


def clean_markdown_stars_v5(text: str) -> str:
    cleaned = re.sub(r"\*\*(?=\S)([^*\n]*?\S)\*\*", r"\1", text)
    return re.sub(
        r"(?<!\*)\*(?=\S)([^*\n]*?\S)\*(?!\*)",
        r"\1",
        cleaned,
    ).strip()


def build_local_fallback_v5(
    user_question: str,
    cards: list[dict[str, Any]],
) -> str:
    names = [card["name"] for card in cards]
    if len(names) >= 3:
        return (
            "По символике этого сочетания здесь нет достаточных оснований считать первый "
            "контакт определённым или близким событием. Расклад оставляет возможность "
            "движения открытой, но не превращает её в достоверный прогноз.\n\n"
            f"{names[0]} задаёт исходный импульс, {names[1]} показывает препятствие или "
            f"резкое изменение этого импульса, а {names[2]} описывает то, что остаётся "
            "после него. Поэтому карты полезнее читать как единый переход от возможности "
            "к помехе и затем к открытому, но ещё не подтверждённому продолжению.\n\n"
            "Проверяемым признаком будет самостоятельная инициатива в реальном общении, "
            "а не само ожидание контакта. Как долго вы готовы оставлять эту возможность "
            "открытой без конкретных действий с другой стороны?"
        )
    return (
        "Расклад не даёт достоверного прогноза будущого действия. Он показывает несколько "
        "символических ракурсов вопроса, которые стоит сверять с известными фактами.\n\n"
        "Карты образуют общий рисунок ситуации, но не раскрывают чужие намерения и сроки.\n\n"
        "Что в реальном общении могло бы подтвердить или опровергнуть ваше ожидание?"
    )


def generate_personal_reading_v5(
    *,
    user_question: str,
    cards: list[dict[str, Any]],
    analysis_call: Callable[[str], str | None],
    editor_call: Callable[[str], str | None],
    topic: str = "general",
) -> dict[str, Any]:
    analysis_raw = analysis_call(build_analysis_prompt_v5(user_question, cards, topic))
    analysis, issues = parse_json_object_v5(analysis_raw)
    if analysis is not None:
        issues.extend(
            validate_analysis_v5(
                analysis, user_question=user_question, cards=cards
            )
        )
    if analysis is None or issues:
        return {
            "text": build_local_fallback_v5(user_question, cards),
            "used_fallback": True,
            "stage": "analysis",
            "issues": list(dict.fromkeys(issues)),
            "ai_requests": 1,
        }

    editor_raw = editor_call(build_editor_prompt_v5(user_question, cards, analysis))
    final_payload, editor_issues = parse_json_object_v5(editor_raw)
    if final_payload is not None:
        editor_issues.extend(validate_final_text_v5(final_payload, cards=cards))
    if final_payload is None or editor_issues:
        return {
            "text": build_local_fallback_v5(user_question, cards),
            "used_fallback": True,
            "stage": "editor",
            "issues": list(dict.fromkeys(editor_issues)),
            "ai_requests": 2,
        }

    return {
        "text": clean_markdown_stars_v5(final_payload["final_text"]),
        "used_fallback": False,
        "stage": "complete",
        "issues": [],
        "ai_requests": 2,
        "analysis": analysis,
    }
