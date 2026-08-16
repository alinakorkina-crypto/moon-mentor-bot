"""Reading Engine v8: one OpenAI request followed by local validation only.

The model receives the complete question, route, cards, positions and allowed
meanings in one prompt and returns ready-to-send prose. Python never rewrites
that prose: it only removes Markdown stars, validates hard safety constraints,
and falls back locally when transport or safety checks fail.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from reading_engine_v6 import (
    clean_stars_v6,
    count_words_v6,
    fallback_v6,
    infer_question_route_v6,
    missing_cards_v6,
    normalize_final_layout_v6,
    normalize_text_v6,
    normalize_topic_v6,
    parse_json_v6,
    prepare_cards_v6,
    split_paragraphs_v6,
)


MODEL_NAME_V8 = "gpt-5.6-terra"
PRICING_AS_OF_V8 = "2026-08-16"

# Standard API prices in USD per one million tokens. Keeping the prices next to
# the experiment makes preview calculations explicit; production can later move
# them to configuration if multiple models are retained.
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
Ты — Moon Mentor, внимательный собеседник, который использует символику карт
Таро как инструмент психологического размышления. Это не буквальное
предсказание будущего и не чтение мыслей другого человека.

Твоя задача — сразу написать готовый ответ пользователю. Внутренне определи
центральный рисунок сочетания, главное противоречие или усиление и связь с
конкретным вопросом, но не показывай служебный анализ.

Требования к готовому тексту:
- 110–160 слов, обычно три коротких абзаца;
- первый абзац прямо, но осторожно отвечает именно на вопрос;
- второй читает все карты как единое сочетание, а не как три справки;
- третий добавляет одну полезную психологическую мысль, основанную только на
  фактах вопроса, и заканчивается одним точным вопросом для размышления;
- используй названия всех карт естественно;
- пиши тепло, легко и по-человечески, без приветствия, заголовков и Markdown.

Нельзя:
- утверждать мысли, чувства, мотивы, страхи, намерения или планы другого человека;
- обещать событие, срок или исход;
- объяснять причины чужого поведения без фактов;
- ставить диагнозы и использовать терапевтические ярлыки;
- решать за пользователя или давать категоричную команду;
- подменять вопрос о чужой инициативе советом пользователю проявиться самому;
- приписывать пользователю стремление, страх, тревогу или скрытую потребность,
  которых он прямо не описывал;
- повторять исходный вопрос отдельным предложением;
- использовать канцелярские обороты вроде «наблюдаемый критерий», «достаточная
  опора», «психологический фокус», «выглядит условным» или «правила игры».

Допустимы «возможно», «скорее», «похоже», «в символике сочетания», если они не
маскируют категоричное предсказание. Верни только объект с полем final_text.
""".strip()


STYLE_EXAMPLES_V8 = {
    "initiative": """
По символике сочетания уверенного указания на первый шаг с его стороны нет,
хотя возможность контакта остаётся открытой.

Маг усиливает тему действия, Повешенный останавливает прямое движение, а Суд
возвращает к теме, которая пока не получила ясного продолжения. Вместе
карты показывают возможность, которой ещё не хватает подтверждения в общении.

Здесь особенно заметно, как много внимания занимает ожидание контакта. Что
помогло бы вам отличить открытую возможность от надежды без подтверждения?
""".strip(),
    "personal_choice_love": """
Этот контакт может быть ценным, но ответ зависит не только от теплоты общения,
а и от того, насколько его ритм подходит вам.

Двойка Кубков подчёркивает близость, Повешенный добавляет состояние паузы, а
Правосудие возвращает к взаимности. Вместе карты показывают, что приятные
моменты и устойчивость связи — не одно и то же.

Смысл расклада не в готовом решении, а в честном сравнении разных сторон
контакта. Какая взаимность нужна вам, чтобы его продолжение ощущалось ценным?
""".strip(),
    "personal_choice_career": """
Предложение выглядит привлекательным, но выбор зависит от того, насколько
понятны реальные условия будущей работы.

Колесо Фортуны открывает тему перемен, Луна оставляет часть картины неясной, а
Император возвращает к структуре роли. Вместе карты переносят внимание с самого
факта перехода на обязанности, ответственность и границы полномочий.

Расклад не выбирает вместо вас, но показывает, какой части решения не хватает
ясности. Какая информация сильнее всего изменила бы вашу оценку предложения?
""".strip(),
    "personal_choice_general": """
Новая возможность может быть интересной, но решение пока зависит от того,
насколько полной станет имеющаяся информация.

Шут поддерживает открытость новому, Луна показывает неполную картину, а
Правосудие возвращает к фактам и условиям. Вместе карты раскрывают разницу между
привлекательностью варианта и тем, что о нём действительно известно.

Здесь полезнее не торопить вывод, а заметить главный пробел в картине. Что
должно проясниться, чтобы решение перестало держаться на догадках?
""".strip(),
}


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
)


def style_example_v8(route: str, topic: str) -> str:
    if route == "initiative":
        return STYLE_EXAMPLES_V8["initiative"]
    return STYLE_EXAMPLES_V8[f"personal_choice_{normalize_topic_v6(topic)}"]


def route_rule_v8(route: str, topic: str) -> str:
    normalized_topic = normalize_topic_v6(topic)
    if route == "initiative":
        return (
            "Ответь, насколько сочетание символически поддерживает возможность "
            "самостоятельного первого шага другого человека. Не переходи к "
            "возможности инициативы пользователя и не делай прогноз по срокам."
        )
    if normalized_topic == "love":
        return (
            "Не решай, продолжать ли контакт. Покажи, какие две стороны связи "
            "нужно сопоставить; не предлагай терпеть или принимать неудобный ритм."
        )
    if normalized_topic == "career":
        return (
            "Не решай, принимать ли предложение. Покажи сильную сторону, главную "
            "неясность и информацию, от которой зависит личный выбор."
        )
    return (
        "Не выбирай за пользователя. Покажи центральное противоречие и условие, "
        "которое может сделать личный выбор яснее."
    )


def build_prompt_v8(
    question: str,
    cards: list[dict[str, Any]],
    route: str,
    topic: str = "general",
) -> str:
    prepared = prepare_cards_v6(cards, route, topic)
    card_block = "\n".join(
        f"- {item['position']}: {item['name']} — {item['meaning']}"
        for item in prepared
    )
    return f"""
Маршрут: {route}
Тема: {normalize_topic_v6(topic)}
Правило этого маршрута: {route_rule_v8(route, topic)}

Вопрос пользователя:
{question}

Карты, их позиции и единственные допустимые символические значения:
{card_block}

Порядок карт — логика сочетания, а не гарантированная последовательность событий.
Не добавляй факты, которых нет в вопросе и значениях карт.

Эталон манеры письма для этого маршрута:
{style_example_v8(route, topic)}

Эталон задаёт только теплоту, прямоту и связность. Не копируй из него карты или
события. Напиши новый готовый ответ именно на текущий вопрос и верни только JSON.
""".strip()


def hard_safety_issues_v8(text: str) -> list[str]:
    normalized = normalize_text_v6(text)
    return [
        f"unsafe:{label}"
        for label, pattern in HARD_SAFETY_PATTERNS_V8
        if re.search(pattern, normalized, re.IGNORECASE)
    ]


def style_warnings_v8(text: str, question: str) -> list[str]:
    normalized = normalize_text_v6(text)
    warnings = [
        label
        for label, pattern in STYLE_WARNING_PATTERNS_V8
        if re.search(pattern, normalized, re.IGNORECASE)
    ]
    words = count_words_v6(text)
    if words < 100 or words > 175:
        warnings.append(f"preferred_word_count:{words}")
    paragraphs = split_paragraphs_v6(text)
    if len(paragraphs) != 3:
        warnings.append(f"preferred_paragraph_count:{len(paragraphs)}")
    if "партнер" in normalized and "партнер" not in normalize_text_v6(question):
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

    text = normalize_final_layout_v6(text)
    normalized = normalize_text_v6(text)
    issues = hard_safety_issues_v8(text)
    words = count_words_v6(text)
    if words < 70 or words > 220:
        issues.append(f"extreme_word_count:{words}")
    if text.count("?") != 1 or not text.rstrip().endswith("?"):
        issues.append(f"question_count:{text.count('?')}")
    missing = missing_cards_v6(text, cards)
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


def unpack_reply_v8(reply: Any) -> tuple[dict[str, Any] | None, dict[str, Any], list[str]]:
    diagnostics = {
        "status": None,
        "model": None,
        "usage": None,
        "cost_usd": None,
    }
    if isinstance(reply, str) or reply is None:
        payload, issues = parse_json_v6(reply)
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

    payload = reply.get("payload")
    if isinstance(payload, dict):
        return payload, diagnostics, []
    raw = reply.get("text")
    payload, issues = parse_json_v6(raw if isinstance(raw, str) else None)
    return payload, diagnostics, issues


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


def fallback_v8(question: str, cards: list[dict[str, Any]], route: str) -> str:
    return fallback_v6(question, cards, route)


def generate_reading_v8(
    *,
    question: str,
    cards: list[dict[str, Any]],
    model_call: Callable[[str], Any],
    topic: str = "general",
) -> dict[str, Any]:
    route = infer_question_route_v6(question)
    if route not in {"initiative", "personal_choice"}:
        return {
            "text": fallback_v8(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "routing",
            "issues": ["unsupported_route"],
            "warnings": [],
            "ai_requests": 0,
            "diagnostics": None,
            "rejected_text": None,
        }

    reply = model_call(build_prompt_v8(question, cards, route, topic))
    payload, diagnostics, issues = unpack_reply_v8(reply)
    warnings: list[str] = []
    rejected_text = None
    if payload is not None:
        text = payload.get("final_text")
        if isinstance(text, str):
            normalized = normalize_final_layout_v6(text)
            payload = {**payload, "final_text": normalized}
            rejected_text = clean_stars_v6(normalized)
        hard_issues, warnings = validate_final_v8(
            payload,
            question=question,
            cards=cards,
            route=route,
        )
        issues.extend(hard_issues)

    if payload is None or issues:
        return {
            "text": fallback_v8(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "generation",
            "issues": list(dict.fromkeys(issues)),
            "warnings": warnings,
            "ai_requests": 1,
            "diagnostics": diagnostics,
            "rejected_text": rejected_text,
        }

    return {
        "text": clean_stars_v6(payload["final_text"]),
        "route": route,
        "used_fallback": False,
        "stage": "complete",
        "issues": [],
        "warnings": warnings,
        "ai_requests": 1,
        "diagnostics": diagnostics,
        "rejected_text": None,
    }


count_words_v8 = count_words_v6
split_paragraphs_v8 = split_paragraphs_v6
clean_stars_v8 = clean_stars_v6
