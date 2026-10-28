"""Reading Engine v8: one OpenAI request followed by local validation only.

The model receives the complete question, route, cards, positions and allowed
meanings in one prompt and returns ready-to-send prose. Python never rewrites
that prose: it only removes Markdown stars, validates hard safety constraints,
and reports transport or safety failures without substituting local prose.
"""

from __future__ import annotations

import re
import json
import unicodedata
from typing import Any, Callable

ROUTE_POSITIONS_V8 = {
    "initiative": (
        "Какой импульс или ожидание связано с возможностью контакта",
        "Что делает эту возможность неясной или противоречивой",
        "На какой внутренний или проверяемый ориентир переносится фокус",
    ),
    "personal_choice": (
        "Что делает рассматриваемый вариант привлекательным или значимым",
        "Главное противоречие, цена или ограничение этого варианта",
        "Какой критерий помогает пользователю определить собственную позицию",
    ),
}

LATIN_TO_CYRILLIC_LOOKALIKES_V8 = str.maketrans(
    {
        "A": "А", "a": "а", "B": "В", "C": "С", "c": "с",
        "E": "Е", "e": "е", "H": "Н", "K": "К", "k": "к",
        "M": "М", "O": "О", "o": "о", "P": "Р", "p": "р",
        "T": "Т", "X": "Х", "x": "х", "Y": "У", "y": "у",
    }
)


def normalize_text_v8(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().replace("ё", "е"))


def normalize_topic_v8(topic: str) -> str:
    normalized = normalize_text_v8(topic)
    if normalized in {"love", "relationship", "relationships", "отношения"}:
        return "love"
    if normalized in {"career", "work", "job", "карьера", "работа"}:
        return "career"
    return "general"


def _infer_specific_route_v8(question: str) -> str:
    q = normalize_text_v8(question)
    initiative_patterns = (
        r"\bвыйд\w*(?:\s+\w+){0,3}\s+на контакт\b",
        r"\bперв\w*\s+на контакт\b",
        r"\bнапиш\w*\b",
        r"\bпозвон\w*\b",
        r"\bпрояв\w*\b",
        r"\bсдела\w*(?:\s+\w+){0,3}\s+перв\w+\s+шаг\b",
        r"\bверн\w*\b",
        r"\bвозобнов\w*\s+общен\w*\b",
    )
    if any(re.search(pattern, q) for pattern in initiative_patterns):
        return "initiative"

    choice_markers = (
        "стоит ли",
        "соглашаться",
        "продолжать ли",
        "принимать ли",
        "уходить ли",
        "выбирать ли",
        "что выбрать",
    )
    if any(marker in q for marker in choice_markers):
        return "personal_choice"
    return "unsupported"


def _prepare_specific_cards_v8(
    cards: list[dict[str, Any]],
    route: str,
    topic: str = "general",
) -> list[dict[str, str]]:
    positions = ROUTE_POSITIONS_V8[route]
    normalized_topic = normalize_topic_v8(topic)
    prepared = []
    for index, card in enumerate(cards):
        prepared.append(
            {
                "name": card["name"],
                "position": (
                    positions[index]
                    if index < len(positions)
                    else f"Дополнительный ракурс {index + 1}"
                ),
                "meaning": (
                    card.get(topic)
                    or card.get(normalized_topic)
                    or card.get("general")
                    or ""
                ),
            }
        )
    return prepared


def word_form_pattern_v8(word: str) -> str:
    escaped = re.escape(word)
    lower = word.lower()
    endings = (
        ("ая", ("ая", "ой", "ую", "ою")),
        ("яя", ("яя", "ей", "юю", "ею")),
        ("ый", ("ый", "ого", "ому", "ым", "ом")),
        ("ий", ("ий", "его", "ему", "им", "ем")),
        ("а", ("а", "ы", "е", "у", "ой", "ою", "ей", "ею")),
        ("я", ("я", "и", "е", "ю", "ей", "ею")),
        ("ь", ("ь", "и", "ью")),
        ("е", ("е", "я", "а", "ю", "у", "ем", "ом")),
        ("о", ("о", "а", "у", "ом", "е")),
        ("й", ("й", "я", "ю", "ем", "е")),
    )
    for ending, forms in endings:
        if lower.endswith(ending) and len(word) > len(ending) + 1:
            return re.escape(word[:-len(ending)]) + "(?:" + "|".join(forms) + ")"
    return escaped + "(?:а|у|ом|е|ы|ов|ам|ами|ах)?"


def card_pattern_v8(name: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", name)
    return rf"(?<!\w){r'[\s–—-]+'.join(word_form_pattern_v8(word) for word in words)}(?!\w)"


def normalize_card_search_v8(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", normalized)
    return normalized.translate(LATIN_TO_CYRILLIC_LOOKALIKES_V8)


def missing_cards_v8(text: str, cards: list[dict[str, Any]]) -> list[str]:
    normalized_text = normalize_card_search_v8(text)
    return [
        card["name"]
        for card in cards
        if not re.search(card_pattern_v8(card["name"]), text, re.IGNORECASE)
        and not re.search(
            card_pattern_v8(normalize_card_search_v8(card["name"])),
            normalized_text,
            re.IGNORECASE,
        )
    ]


def count_words_v8(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?", text))


def split_paragraphs_v8(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    return [
        part.strip()
        for part in re.split(r"\n[ \t]*\n+", normalized)
        if part.strip()
    ]


def normalize_final_layout_v8(text: str) -> str:
    normalized = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    normalized = re.sub(r"\r\n?", "\n", normalized).strip()
    paragraphs = split_paragraphs_v8(normalized)
    if len(paragraphs) == 3:
        return "\n\n".join(paragraphs)

    nonempty_lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if len(nonempty_lines) == 3:
        return "\n\n".join(nonempty_lines)
    return normalized


MODEL_NAME_V8 = "gpt-5.6-terra"
PRICING_AS_OF_V8 = "2026-08-16"

# Standard API prices in USD per one million tokens for internal cost diagnostics.
MODEL_PRICING_V8 = {
    "gpt-5.6-terra": {
        "input": 2.00,
        "cached_input": 0.20,
        "output": 12.00,
    },
    "gpt-5.6-luna": {
        "input": 0.20,
        "cached_input": 0.02,
        "output": 1.20,
    },
    "gpt-5.6-sol": {
        "input": 5.00,
        "cached_input": 0.50,
        "output": 30.00,
    },
    # The API alias for the Sol tier.
    "gpt-5.6": {
        "input": 5.00,
        "cached_input": 0.50,
        "output": 30.00,
    },
}


FINAL_SCHEMA_V8 = {
    "type": "object",
    "properties": {"final_text": {"type": "string"}},
    "required": ["final_text"],
    "additionalProperties": False,
}


SYSTEM_PROMPT_V8 = """
Ты — Moon Mentor, внимательный и проницательный собеседник, который хорошо понимает символику Таро.

Ответь на вопрос пользователя ясно и по существу. В начале дай понятный вывод по сочетанию карт. Если карты противоречат друг другу, покажи, в какую сторону всё же сильнее склоняется расклад и что создаёт неопределённость.

Свяжи карты в одну живую историю, сохраняя их порядок. Используй переданные значения как смысловые опоры, но не пересказывай их механически. Объясняй простыми словами и конкретными глаголами. Не повторяй один вывод несколько раз.

Трактуй карты символически: не выдавай предположение за установленный факт, не утверждай, что точно знаешь чужие мысли или будущее. Можно говорить, что карта показывает импульс, остановку, дистанцию, надежду или противоречие, но не приписывать человеку точные мотивы без фактов.

Пиши естественным разговорным русским языком, тепло и без пафоса. Обычно два коротких абзаца и 70–130 слов. Не добавляй совет или вопрос пользователю, если они не нужны для ответа.

Верни только JSON-объект с полем final_text.
""".strip()


HARD_SAFETY_PATTERNS_V8 = (
    (
        "mind_reading",
        r"\b(?:он|она|человек)\s+(?:на самом деле\s+)?"
        r"(?:думает|чувствует|хочет|боится|планирует|решил[аи]?)\b",
    ),
    (
        "certain_future",
        r"\b(?:он|она|человек)\s+(?:точно|обязательно|непременно)\s+"
        r"(?:напишет|позвонит|верн[её]тся|проявится|выйдет)\b",
    ),
    ("guarantee", r"\b(?:карты|расклад)\s+(?:гарантируют|обещают|подтверждают)\b"),
    (
        "diagnosis",
        r"\b(?:у вас|у тебя)\s+(?:травма|зависимость|созависимость|"
        r"контрзависимость|расстройство)\b",
    ),
    ("manipulation", r"\b(?:спровоцируй|вызови ревность|заставь его|манипулируй)\b"),
    (
        "decision_for_user",
        r"(?:^|[.!?]\s+)(?:вам|тебе)\s+(?:нужно|необходимо|следует)\s+"
        r"(?:согласиться|отказаться|продолжать|прекратить|уйти|остаться)\b",
    ),
)


STYLE_WARNING_PATTERNS_V8 = (
    ("bureaucratic", r"\b(?:наблюдаем\w*\s+критери\w*|достаточн\w*\s+опор\w*|психологическ\w*\s+фокус\w*)\b"),
    ("therapy_style", r"\b(?:внутренн\w*\s+потребност\w*|безопасн\w*\s+для\s+вас|границ\w*\s+выносливост\w*)\b"),
    ("cliche_rules_game", r"\bправил\w*\s+игр\w*\b"),
    ("cliche_movement_topic", r"\bсаму\s+тему\s+движения\b"),
    ("cliche_impulse_development", r"\bпрямое\s+развитие\s+импульса\b"),
    ("cliche_practical_step", r"\bсостоявшийся\s+практический\s+шаг\b"),
    ("cliche_open_possibility", r"\bвозможность\s+оста[её]тся\s+открытой\b"),
    ("cliche_unconfirmed", r"\bнельзя\s+считать\s+подтвержд[её]нной\b"),
    ("cliche_symbolic_uncertainty", r"\bпо\s+символике\s+сочетания\s+нельзя\s+уверенно\s+сказать\b"),
    ("service_conclusion_label", r"\bитог\s*:"),
)


OPEN_QUESTION_POSITIONS_V8 = (
    "основа ситуации",
    "главное напряжение",
    "направление развития",
)


def infer_question_route_v8(question: str) -> str:
    route = _infer_specific_route_v8(question)
    return route if route in {"initiative", "personal_choice"} else "open_question"


def prepare_cards_v8(
    cards: list[dict[str, Any]], route: str, topic: str = "general",
) -> list[dict[str, str]]:
    normalized_topic = normalize_topic_v8(topic)
    if route != "open_question":
        return _prepare_specific_cards_v8(cards, route, normalized_topic)
    return [
        {
            "name": card["name"],
            "position": (OPEN_QUESTION_POSITIONS_V8[index] if index < 3
                         else f"Дополнительный ракурс {index + 1}"),
            "meaning": card.get(normalized_topic) or card.get("general") or "",
        }
        for index, card in enumerate(cards)
    ]


def route_rule_v8(route: str, topic: str) -> str:
    if route == "initiative":
        return "Оцени, поддерживает ли сочетание первый шаг другого человека; не переноси инициативу на пользователя"
    normalized_topic = normalize_topic_v8(topic)
    if route == "open_question":
        rule = {
            "general": "Прямо раскрой главный смысл сочетания относительно вопроса.",
            "love": "Опиши динамику отношений символически, не утверждая чужие чувства и мысли как факт.",
            "career": "Раскрой рабочую ситуацию, сильную сторону, риск и направление.",
        }[normalized_topic]
        return rule + " Не превращай ответ в совет, если пользователь его не просил."
    if normalized_topic == "love":
        return "Сопоставь стороны связи, не решая за пользователя и не советуя терпеть неудобный ритм."
    if normalized_topic == "career":
        return "Покажи плюс предложения, главную неясность и нужные для выбора сведения; не решай за пользователя."
    return "Покажи противоречие и условие ясного выбора; не выбирай за пользователя."


def build_prompt_v8(
    question: str,
    cards: list[dict[str, Any]],
    route: str,
    topic: str = "general",
) -> str:
    prepared = prepare_cards_v8(cards, route, topic)
    card_block = "\n".join(
        f"- {item['position']}: {item['name']} — {item['meaning']}"
        for item in prepared
    )
    return f"""
Маршрут: {route}
Правило этого маршрута: {route_rule_v8(route, topic)}

Вопрос пользователя:
{question}

Смысловые опоры для трактовки:
{card_block}

Сохрани порядок карт.
Свяжи их в единый ответ на вопрос.
Не добавляй неизвестные факты.
""".strip()


def hard_safety_issues_v8(text: str) -> list[str]:
    normalized = normalize_text_v8(text)
    return [
        f"unsafe:{label}"
        for label, pattern in HARD_SAFETY_PATTERNS_V8
        if re.search(pattern, normalized, re.IGNORECASE)
    ]


def style_warnings_v8(text: str, question: str) -> list[str]:
    normalized = normalize_text_v8(text)
    warnings = [
        label
        for label, pattern in STYLE_WARNING_PATTERNS_V8
        if re.search(pattern, normalized, re.IGNORECASE)
    ]
    probability_words = re.findall(r"\b(?:возможност|потенциал|вероятност)\w*\b", normalized)
    if len(probability_words) > 1:
        warnings.append("repeated_probability_words")
    words = count_words_v8(text)
    if words < 70 or words > 130:
        warnings.append(f"preferred_word_count:{words}")
    paragraphs = split_paragraphs_v8(text)
    if len(paragraphs) != 2:
        warnings.append(f"preferred_paragraph_count:{len(paragraphs)}")
    if "партнер" in normalized and "партнер" not in normalize_text_v8(question):
        warnings.append("unsupported_role:partner")
    return list(dict.fromkeys(warnings))


def validate_final_v8(
    payload: dict[str, Any],
    *,
    question: str,
    cards: list[dict[str, Any]],
    route: str,
) -> tuple[list[str], list[str]]:
    unexpected = set(payload) - {"final_text"}
    if unexpected:
        return ["unexpected_fields:" + "|".join(sorted(unexpected))], []
    text = payload.get("final_text")
    if not isinstance(text, str) or not text.strip():
        return ["missing:final_text"], []

    text = normalize_final_layout_v8(text)
    normalized = normalize_text_v8(text)
    issues = hard_safety_issues_v8(text)
    words = count_words_v8(text)
    if words < 55 or words > 180:
        issues.append(f"extreme_word_count:{words}")
    paragraphs = split_paragraphs_v8(text)
    if not 1 <= len(paragraphs) <= 3:
        issues.append(f"paragraph_count:{len(paragraphs)}")
    if text.count("?") > 1:
        issues.append(f"question_count:{text.count('?')}")
    missing = missing_cards_v8(text, cards)
    if missing:
        issues.append("final_missing_cards:" + "|".join(missing))
    if re.match(r"\s*(?:привет|здравствуйте|приветствую)\b", text, re.IGNORECASE):
        issues.append("greeting")
    if route == "initiative":
        if re.search(r"\bваш\w*\s+(?:собственн\w*\s+)?инициатив\w*\b", normalized):
            issues.append("initiative_shift_to_user")
        unsupported_states = (
            r"\bваш\w*\s+(?:сильн\w*\s+)?(?:желани\w*|стремлени\w*)\s+"
            r"(?:сдвинуть|ускорить|сблизиться|к\s+сближению)\b"
        )
        if re.search(unsupported_states, normalized):
            issues.append("unsupported_user_state")
    return list(dict.fromkeys(issues)), style_warnings_v8(text, question)


def parse_json_v8(raw: str | None) -> tuple[dict[str, Any] | None, list[str]]:
    """Decode JSON without normalizing any characters inside string values."""
    if not isinstance(raw, str) or not raw.strip():
        return None, ["empty_answer"]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, ["invalid_json"]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    return payload, []


def unpack_reply_v8(reply: Any) -> tuple[dict[str, Any] | None, dict[str, Any], list[str]]:
    diagnostics = {
        "status": None,
        "model": None,
        "usage": None,
        "cost_usd": None,
    }
    if isinstance(reply, str) or reply is None:
        payload, issues = parse_json_v8(reply)
        return payload, diagnostics, issues
    if not isinstance(reply, dict):
        return None, diagnostics, ["unsupported_reply_type"]

    diagnostics.update(
        {
            "status": reply.get("status"),
            "model": reply.get("model"),
            "usage": reply.get("usage"),
        }
    )
    model = diagnostics["model"] or MODEL_NAME_V8
    diagnostics["cost_usd"] = calculate_cost_v8(diagnostics["usage"], model)

    status = reply.get("status")
    status_issues = list(reply.get("issues") or [])
    if status is not None and status != "completed":
        status_issues.append("response_not_completed")
    if reply.get("error_type"):
        diagnostics["error_type"] = reply["error_type"]
    if reply.get("error_message") is not None:
        diagnostics["error_message"] = reply["error_message"]
    payload = reply.get("payload")
    if isinstance(payload, dict):
        return payload, diagnostics, status_issues
    raw = reply.get("raw_response_text", reply.get("text"))
    payload, issues = parse_json_v8(raw if isinstance(raw, str) else None)
    return payload, diagnostics, status_issues + issues


def calculate_cost_v8(usage: Any, model: str = MODEL_NAME_V8) -> float | None:
    if not isinstance(usage, dict) or model not in MODEL_PRICING_V8:
        return None
    prices = MODEL_PRICING_V8[model]
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cached_tokens = min(int(usage.get("cached_input_tokens") or 0), input_tokens)
    regular_input = input_tokens - cached_tokens
    return (
        regular_input * prices["input"]
        + cached_tokens * prices["cached_input"]
        + output_tokens * prices["output"]
    ) / 1_000_000


def clean_stars_v8(text: str) -> str:
    """Remove paired emphasis markers, preserving all other characters."""
    cleaned = re.sub(r"\*\*(?=\S)([^*\n]*?\S)\*\*", r"\1", text)
    return re.sub(r"(?<!\*)\*(?=\S)([^*\n]*?\S)\*(?!\*)", r"\1", cleaned)


def generate_reading_v8(
    *,
    question: str,
    cards: list[dict[str, Any]],
    model_call: Callable[[str], Any],
    topic: str = "general",
) -> dict[str, Any]:
    route = infer_question_route_v8(question)

    try:
        reply = model_call(build_prompt_v8(question, cards, route, topic))
    except Exception as error:
        reply = {"status": "ERROR", "error_type": type(error).__name__}
    raw_response_text = (
        reply if isinstance(reply, str) else
        reply.get("raw_response_text", reply.get("text")) if isinstance(reply, dict) else None
    )
    payload, diagnostics, issues = unpack_reply_v8(reply)
    warnings: list[str] = []
    rejected_text = None
    if payload is not None:
        text = payload.get("final_text")
        if isinstance(text, str):
            rejected_text = text
        hard_issues, warnings = validate_final_v8(
            payload,
            question=question,
            cards=cards,
            route=route,
        )
        issues.extend(hard_issues)

    if payload is None or issues:
        return {
            "text": None,
            "route": route,
            "status": "error" if (
                payload is None or "schema_validation_error" in issues
                or diagnostics.get("status") not in (None, "completed")
            ) else "rejected",
            "stage": "generation",
            "issues": list(dict.fromkeys(issues)),
            "warnings": warnings,
            "ai_requests": 1,
            "diagnostics": diagnostics,
            "rejected_text": rejected_text,
            "raw_response_text": raw_response_text,
        }

    return {
        "text": clean_stars_v8(payload["final_text"]),
        "route": route,
        "status": "success",
        "stage": "complete",
        "issues": [],
        "warnings": warnings,
        "ai_requests": 1,
        "diagnostics": diagnostics,
        "rejected_text": None,
        "raw_response_text": raw_response_text,
    }
