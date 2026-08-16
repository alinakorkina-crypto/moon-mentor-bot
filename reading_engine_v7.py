"""Reading Engine v7.1: evidence-anchored brief plus natural-language editor.

This experiment deliberately keeps the two-call architecture while changing the
job of the first call.  The analyst now produces a small, meaningful reading
brief instead of reducing the spread to classification codes.  In v7.1 the
reflection is anchored to an exact phrase from the user's question and the model
may not invent a psychological explanation.  Python validates transport,
structure and safety; stylistic imperfections remain warnings.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from reading_engine_v6 import (
    clean_stars_v6,
    count_words_v6,
    decorate_transport_issues_v6,
    fallback_v6,
    infer_question_route_v6,
    missing_cards_v6,
    normalize_final_layout_v6,
    normalize_text_v6,
    normalize_topic_v6,
    parse_json_v6,
    prepare_cards_v6,
    split_paragraphs_v6,
    unpack_reply_v6,
)


ANALYSIS_SYSTEM_V7 = """
Ты — аналитик Moon Mentor. Moon Mentor использует символику Таро как способ
посмотреть на ситуацию с нового ракурса, а не как достоверный прогноз или чтение
чужих мыслей.

Создай короткий содержательный бриф для редактора и верни только JSON:

- question_route — переданный маршрут;
- direct_answer — осторожный, но настоящий ответ на вопрос. Используй «скорее»,
  «возможно», «похоже», «карты не дают уверенного указания», если это уместно;
- card_roles — название каждой карты и только её функция в сочетании: opens,
  limits, reframes, balances или reinforces. Не переписывай значение карты;
- central_dynamic — как карты взаимодействуют: что усиливается, чему
  противоречит или что меняет общий рисунок;
- question_quote — одна точная непрерывная цитата из вопроса пользователя;
- reflection_question — один вопрос для размышления, основанный только на этой
  цитате. Формулируй вопрос, а не психологическое утверждение.

Не пиши готовый расклад. Не приписывай пользователю стремление форсировать
события, тревогу, перенос ответственности, пассивное ожидание, попытку изменить
другого или иное внутреннее состояние, которого нет в точной цитате. Не
приписывай другому человеку мысли, чувства, мотивы, страхи, намерения или будущие
действия. Не обещай событие и не принимай решение за пользователя. Допустимо
описывать вероятность и одну символическую версию без гарантии.
""".strip()


EDITOR_SYSTEM_V7 = """
Ты — автор Moon Mentor: внимательный, живой собеседник, который умеет читать
сочетание карт как единый психологический сюжет. Получи вопрос, карты и
проверенный аналитический бриф. Верни только JSON с полем final_text.

Напиши цельный ответ на 130–170 слов, обычно в трёх небольших абзацах.

1. Сразу дай осторожный ответ на вопрос. Не прячь его за длинной оговоркой.
   Можно говорить «скорее», «возможно», «похоже», «возможность остаётся».
2. Покажи, как все карты работают вместе. Не делай три словарные справки и не
   превращай их порядок в достоверную хронологию событий.
3. Мягко переведи расклад к вопросу пользователя, используя только переданную
   цитату и reflection_question. Не объявляй внутреннее состояние фактом.
   Закончи одним точным вопросом, не давай команд и не решай за человека.

Пиши тепло, легко и естественно, как хороший собеседник, а не как валидатор или
официальный отчёт. Не используй слова «маршрут», «критерий», «проверяемое
подтверждение», «достаточная опора», «символическая поддержка», «выглядит
условным», «объективный ориентир», «психологический фокус». Не цитируй вопрос
дословно. Не начинай с приветствия и не добавляй дисклеймер отдельным абзацем.

Нельзя утверждать как факт, что другой человек думает, чувствует, хочет, боится,
планирует или обязательно совершит действие. Нельзя придумывать причины его
поведения, ставить диагнозы, обещать сроки и исходы, советовать манипуляцию или
принимать решение за пользователя. Не называй человека партнёром, если это не
сказано в вопросе. Не предлагай принять неудобный формат как данность. Используй
только данные вопроса, исходные значения карт и проверенный бриф.
""".strip()


ANALYSIS_SCHEMA_V7 = {
    "type": "object",
    "properties": {
        "question_route": {"type": "string"},
        "direct_answer": {"type": "string"},
        "card_roles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "card": {"type": "string"},
                    "function": {"type": "string"},
                },
                "required": ["card", "function"],
            },
        },
        "central_dynamic": {"type": "string"},
        "question_quote": {"type": "string"},
        "reflection_question": {"type": "string"},
    },
    "required": [
        "question_route",
        "direct_answer",
        "card_roles",
        "central_dynamic",
        "question_quote",
        "reflection_question",
    ],
}


EDITOR_SCHEMA_V7 = {
    "type": "object",
    "properties": {"final_text": {"type": "string"}},
    "required": ["final_text"],
}


STYLE_EXAMPLES_V7 = {
    "initiative": """
Вопрос: «Проявится ли человек сам?»
Карты: Маг — Повешенный — Суд

Возможность инициативы здесь есть, но карты не показывают её как лёгкий и уже
определившийся шаг. Скорее ситуация остаётся открытой: импульс к проявлению
возникает, однако пока не получает свободного развития.

Маг усиливает тему действия и первого шага, Повешенный ограничивает прямое
движение, а Суд сохраняет возможность вернуться к теме. Вместе они говорят не о
гарантированном событии, а о противоречии между импульсом и отсутствием ясного
действия.

При этом ожидание чужого шага тоже становится частью этой истории. Какое
конкретное действие ты сама сочтёшь настоящей инициативой, а не случайным знаком?
""".strip(),
    "personal_choice_love": """
Вопрос: «Стоит ли продолжать общение, если оно держится в основном на мне?»
Карты: Двойка Кубков — Повешенный — Правосудие

Этот контакт может оставаться ценным, но карты предлагают смотреть не только на
теплоту между вами, а и на то, насколько связь поддерживается с обеих сторон.

Двойка Кубков подчёркивает притяжение и значимость общения, Повешенный добавляет
состояние зависания, а Правосудие возвращает к вопросу равновесия. В сочетании
они показывают разницу между приятными моментами и устойчивой взаимностью — одно
не всегда означает другое.

Здесь нет готового решения за тебя, но есть точка для честного сравнения: тёплые
моменты и наблюдаемая взаимность в контакте. Какая взаимность нужна тебе, чтобы
продолжение этой связи действительно ощущалось ценным?
""".strip(),
    "personal_choice_career": """
Вопрос: «Стоит ли принимать новое предложение о работе?»
Карты: Колесо Фортуны — Луна — Император

Возможность выглядит привлекательной, но окончательный выбор во многом зависит
от того, насколько ясными окажутся условия, стоящие за обещанием перемен.

Колесо Фортуны открывает тему нового поворота, Луна оставляет часть картины в
неопределённости, а Император требует формы и структуры. Вместе карты смещают
внимание с самого факта перемен на то, можно ли понять будущую роль, ответственность
и границы полномочий.

Расклад не выбирает вместо тебя, но показывает, где сейчас не хватает опоры для
решения. Какая информация о предложении сильнее всего изменила бы твою оценку?
""".strip(),
    "personal_choice_general": """
Вопрос: «Стоит ли соглашаться, если мне пока не хватает информации?»
Карты: Шут — Луна — Правосудие

Новый вариант может быть интересным, но карты оставляют решение открытым до тех
пор, пока главная неопределённость не станет понятнее.

Шут поддерживает готовность попробовать новое, Луна показывает неполную картину,
а Правосудие возвращает к фактам и условиям выбора. Их сочетание говорит не
«да» или «нет», а о разнице между привлекательностью возможности и тем, что о
ней действительно известно.

Возможно, сейчас важнее не торопить ответ, а увидеть, какой информации не хватает
именно тебе. Что должно проясниться, чтобы решение перестало держаться на догадках?
""".strip(),
}


CARD_FUNCTIONS_V7 = {"opens", "limits", "reframes", "balances", "reinforces"}


def route_guardrails_v7(route: str, topic: str) -> str:
    if route == "initiative":
        return (
            "Не приписывай пользователю желание ускорить или форсировать события. "
            "Не придумывай внешние обстоятельства, внутренние барьеры, крушение "
            "планов, быстрый или далёкий срок контакта. Не ставь перед выбором "
            "«написать самой или отпустить». Разрешённый психологический ракурс — "
            "только различие между возможностью контакта и тем действием, которое "
            "пользователь сочтёт инициативой."
        )
    if normalize_topic_v6(topic) == "love":
        return (
            "Не предлагай принять паузы или неудобный ритм как данность. Не называй "
            "их неизбежными или неотъемлемыми, не утверждай тревогу, ранимость, "
            "границы выносливости или попытку переделать другого. Разрешённый "
            "психологический ракурс — потребности пользователя во взаимности, "
            "регулярности и подходящем формате контакта."
        )
    if normalize_topic_v6(topic) == "career":
        return (
            "Не принимай карьерное решение за пользователя. Связывай размышление "
            "только с указанными в вопросе условиями и конкретикой роли."
        )
    return (
        "Не придумывай внутреннее состояние пользователя. Связывай размышление "
        "только с точной цитатой из вопроса и наблюдаемыми условиями выбора."
    )


def fixed_unknowns_v7(route: str, topic: str) -> list[str]:
    if route == "initiative":
        return [
            "мысли, чувства и намерения другого человека",
            "срок и сам факт будущего контакта",
            "причины отсутствия инициативы",
        ]
    if normalize_topic_v6(topic) == "love":
        return [
            "причины поведения другого человека",
            "изменится ли формат контакта в будущем",
        ]
    return ["будущий исход решения", "обстоятельства, которых нет в вопросе"]


def fixed_reality_anchor_v7(route: str, topic: str) -> str:
    if route == "initiative":
        return (
            "самостоятельное содержательное сообщение, звонок или продолжение "
            "разговора без предварительного шага пользователя"
        )
    if normalize_topic_v6(topic) == "love":
        return "наблюдаемая взаимность, инициатива и регулярность контакта"
    if normalize_topic_v6(topic) == "career":
        return "конкретные обязанности, полномочия, подчинение и условия роли"
    return "конкретный факт или условие, которое можно проверить в реальности"


HARD_SAFETY_PATTERNS_V7 = (
    ("mind_reading", r"\b(?:он|она|человек)\s+(?:на самом деле\s+)?(?:думает|чувствует|хочет|боится|планирует|решил[аи]?)\b"),
    ("certain_future", r"\b(?:он|она|человек)\s+(?:точно|обязательно|непременно)\s+(?:напишет|позвонит|верн[её]тся|проявится|выйдет)\b"),
    ("guarantee", r"\b(?:карты|расклад)\s+(?:гарантируют|обещают|подтверждают)\b"),
    ("diagnosis", r"\b(?:у вас|у тебя)\s+(?:травма|зависимость|созависимость|контрзависимость|расстройство)\b"),
    ("manipulation", r"\b(?:спровоцируй|вызови ревность|заставь его|манипулируй)\b"),
    ("decision_for_user", r"(?:^|[.!?]\s+)(?:вам|тебе)\s+(?:нужно|необходимо|следует)\s+(?:согласиться|отказаться|продолжать|прекратить|уйти|остаться)\b"),
    ("unsupported:forcing_events", r"\b(?:форсиров\w*|ускорить)\s+(?:событи\w*|ситуаци\w*)\b"),
    ("unsupported:inner_barriers", r"\bвнутренн\w*\s+барьер\w*\b"),
    ("unsupported:external_circumstances", r"\bвнешн\w*\s+обстоятельств\w*\b"),
    ("unsupported:long_term", r"\bдолгосрочн\w*\b"),
    ("unsupported:plans_collapse", r"\b(?:крушени\w*|разрушени\w*)\s+(?:этих\s+)?план\w*\b"),
    ("unsupported:avoid_uncertainty", r"\bизбежа?\w*\s+неопредел[её]нност\w*\b"),
    ("unsupported:shift_responsibility", r"\b(?:переклад\w*|перелож\w*)\s+ответственност\w*\b"),
    ("unsupported:passive_waiting", r"\bпассивн\w*\s+ожидани\w*\b"),
    ("unsupported:endurance", r"\bграниц\w*\s+выносливост\w*\b"),
    ("unsupported:strong_anxiety", r"\bсильн\w*\s+тревог\w*\b"),
    ("unsupported:integral_pattern", r"\bнеотъемлем\w*\s+част\w*\b"),
    ("unsupported:inevitable", r"\bнеизбежн\w*\b"),
    ("unsupported:self_harm_metaphor", r"\bне\s+ранить\s+себя\b"),
    ("unsupported:change_other", r"\bпеределать\s+чуж\w*\s+(?:темп|ритм)\b"),
    ("unsupported:accept_as_given", r"\bпринять\w*(?:\s+\w+){0,5}\s+как\s+данност\w*\b"),
    ("unsupported:withdrawal_cause", r"\bуход\w*\s+в\s+себя\b"),
    ("unsupported:waiting_drains", r"\bожидани\w*(?:\s+\w+){0,4}\s+забира\w*(?:\s+\w+){0,2}\s+сил\w*\b"),
    ("unsupported:user_impulse", r"\bваш\w*(?:\s+\w+){0,2}\s+внутренн\w*\s+импульс\w*\b"),
    ("unsupported:hurry_desire", r"\bжелани\w*\s+поскорее\b"),
    ("unsupported:expectations_vs_reality", r"\b(?:ожидани\w*(?:\s+\w+){0,4}\s+сталкива\w*|столкновени\w*(?:\s+\w+){0,4}\s+ожидани\w*)(?:\s+\w+){0,3}\s+реальност\w*\b"),
    ("unsupported:quick_contact", r"\bбыстр\w*(?:\s+\w+){0,2}\s+(?:контакт|развити\w*)(?:\s+\w+){0,3}\s+маловероят\w*\b"),
    ("unsupported:beautiful_dreams", r"\bкрасив\w*\s+мечт\w*\b"),
    ("unsupported:waiting_anxiety", r"\bожидани\w*(?:\s+\w+){0,5}\s+тревог\w*\b"),
)


STYLE_WARNING_PATTERNS_V7 = (
    ("bureaucratic:dostatochnaya_opora", r"\bдостаточн\w*\s+опор\w*\b"),
    ("bureaucratic:observable_criterion", r"\bнаблюдаем\w*\s+(?:критери\w*|подтверждени\w*)\b"),
    ("bureaucratic:symbolic_support", r"\bсимволическ\w*\s+поддержк\w*\b"),
    ("bureaucratic:conditional_appearance", r"\bвыглядит\s+условн\w*\b"),
    ("bureaucratic:objective_guide", r"\bобъективн\w*\s+ориентир\w*\b"),
    ("meta:psychological_focus", r"\bпсихологическ\w*\s+фокус\w*\b"),
    ("report_language", r"\bпроверяем\w*\s+подтверждени\w*\b"),
    ("therapy_style:ecological", r"\bэкологичн\w*\b"),
    ("therapy_style:safe", r"\b(?:уверенн\w*\s+и\s+безопасн\w*|чувствовать\s+себя\s+безопасн\w*)\b"),
)


def style_example_v7(route: str, topic: str) -> str:
    if route == "initiative":
        return STYLE_EXAMPLES_V7["initiative"]
    return STYLE_EXAMPLES_V7[f"personal_choice_{normalize_topic_v6(topic)}"]


def build_analysis_prompt_v7(
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
    route_rule = (
        "Ответь, насколько сочетание поддерживает возможность самостоятельной "
        "инициативы, но не предсказывай действие другого человека."
        if route == "initiative"
        else "Не выбирай за пользователя. Покажи, от какого условия или внутреннего приоритета зависит его решение."
    )
    return f"""
Маршрут: {route}
Тема: {normalize_topic_v6(topic)}
Правило маршрута: {route_rule}

Ограничения именно для этого маршрута:
{route_guardrails_v7(route, topic)}

Вопрос пользователя:
{question}

Карты, их аналитические позиции и допустимые значения:
{card_block}

Собери содержательный бриф именно для этого вопроса. Для каждой карты выбери
только функцию из списка opens, limits, reframes, balances, reinforces. Не
создавай новое значение карты: редактор получит исходные значения отдельно.
central_dynamic связывает карты, но не вводит новые события или психологические
причины. question_quote должна дословно встречаться в вопросе пользователя, а
reflection_question может опираться только на неё. Верни только JSON.
""".strip()


def build_editor_prompt_v7(
    question: str,
    cards: list[dict[str, Any]],
    route: str,
    analysis: dict[str, Any],
    topic: str = "general",
) -> str:
    source = {
        "question": question,
        "topic": normalize_topic_v6(topic),
        "cards": prepare_cards_v6(cards, route, topic),
        "brief": analysis,
        "unknowns_to_keep_open": fixed_unknowns_v7(route, topic),
        "reality_anchor": fixed_reality_anchor_v7(route, topic),
        "route_guardrails": route_guardrails_v7(route, topic),
    }
    return f"""
Материалы текущего расклада:
{json.dumps(source, ensure_ascii=False, indent=2)}

Эталон уровня теплоты, связности и прямоты:
{style_example_v7(route, topic)}

Эталон показывает только манеру письма. Не копируй из него карты, события или
формулировки. Напиши новый ответ только по материалам текущего расклада. Верни
только JSON.
""".strip()


def combined_analysis_text_v7(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in (
        "direct_answer",
        "central_dynamic",
        "question_quote",
        "reflection_question",
    ):
        value = payload.get(field)
        if isinstance(value, str):
            parts.append(value)
    return " ".join(parts)


def hard_safety_issues_v7(text: str) -> list[str]:
    normalized = normalize_text_v6(text)
    return [
        f"unsafe:{label}"
        for label, pattern in HARD_SAFETY_PATTERNS_V7
        if re.search(pattern, normalized, re.IGNORECASE)
    ]


def style_warnings_v7(text: str, question: str) -> list[str]:
    normalized = normalize_text_v6(text)
    warnings = [
        label
        for label, pattern in STYLE_WARNING_PATTERNS_V7
        if re.search(pattern, normalized, re.IGNORECASE)
    ]
    if "партнер" in normalized and "партнер" not in normalize_text_v6(question):
        warnings.append("unsupported_role:partner")
    if normalized.count("?") > 1:
        warnings.append("multiple_questions")
    words = count_words_v6(text)
    if words < 110 or words > 190:
        warnings.append(f"preferred_word_count:{words}")
    paragraphs = split_paragraphs_v6(text)
    if len(paragraphs) != 3:
        warnings.append(f"preferred_paragraph_count:{len(paragraphs)}")
    return list(dict.fromkeys(warnings))


def validate_analysis_v7(
    payload: dict[str, Any],
    *,
    question: str,
    cards: list[dict[str, Any]],
    route: str,
) -> list[str]:
    issues: list[str] = []
    expected = set(ANALYSIS_SCHEMA_V7["required"])
    unexpected = set(payload) - expected
    if unexpected:
        issues.append("unexpected_analysis_fields:" + "|".join(sorted(unexpected)))
    if payload.get("question_route") != route:
        issues.append("route_mismatch")

    for field in (
        "direct_answer",
        "central_dynamic",
        "question_quote",
        "reflection_question",
    ):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            issues.append(f"missing:{field}")

    roles = payload.get("card_roles")
    expected_names = [card["name"] for card in cards]
    if not isinstance(roles, list) or len(roles) != len(expected_names):
        issues.append("invalid:card_roles")
    else:
        actual_names = []
        for item in roles:
            if not isinstance(item, dict):
                issues.append("invalid:card_role")
                continue
            actual_names.append(item.get("card"))
            if item.get("function") not in CARD_FUNCTIONS_V7:
                issues.append("invalid:card_function")
        if actual_names != expected_names:
            issues.append("analysis_card_order_or_names")

    quote = payload.get("question_quote")
    if isinstance(quote, str) and normalize_text_v6(quote) not in normalize_text_v6(question):
        issues.append("unsupported_question_quote")

    if isinstance(payload.get("reflection_question"), str) and not payload[
        "reflection_question"
    ].rstrip().endswith("?"):
        issues.append("analysis_missing_question")

    issues.extend(hard_safety_issues_v7(combined_analysis_text_v7(payload)))
    return list(dict.fromkeys(issues))


def validate_final_v7(
    payload: dict[str, Any],
    *,
    question: str,
    cards: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    text = payload.get("final_text")
    if not isinstance(text, str) or not text.strip():
        return ["missing:final_text"], []

    text = normalize_final_layout_v6(text)
    issues = hard_safety_issues_v7(text)
    words = count_words_v6(text)
    if words < 70 or words > 240:
        issues.append(f"extreme_word_count:{words}")
    if not text.rstrip().endswith("?"):
        issues.append("missing_final_question")
    missing = missing_cards_v6(text, cards)
    if missing:
        issues.append("final_missing_cards:" + "|".join(missing))
    if re.match(r"\s*(?:привет|здравствуйте|приветствую)\b", text, re.IGNORECASE):
        issues.append("greeting")
    return list(dict.fromkeys(issues)), style_warnings_v7(text, question)


def fallback_v7(question: str, cards: list[dict[str, Any]], route: str) -> str:
    """Keep a safe local answer for transport failures without pretending it is AI."""
    # V6 already has route-aware, card-complete fallbacks.  Reuse them only for
    # genuine technical or safety failures; style warnings never trigger this path.
    return fallback_v6(question, cards, route)


def generate_reading_v7(
    *,
    question: str,
    cards: list[dict[str, Any]],
    analysis_call: Callable[[str], Any],
    editor_call: Callable[[str], Any],
    topic: str = "general",
) -> dict[str, Any]:
    route = infer_question_route_v6(question)
    if route not in {"initiative", "personal_choice"}:
        return {
            "text": fallback_v7(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "routing",
            "issues": ["unsupported_route"],
            "warnings": [],
            "ai_requests": 0,
            "analysis_diagnostics": None,
            "editor_diagnostics": None,
        }

    analysis_reply = analysis_call(build_analysis_prompt_v7(question, cards, route, topic))
    analysis_raw, analysis_diagnostics = unpack_reply_v6(analysis_reply)
    analysis, issues = parse_json_v6(analysis_raw)
    issues = decorate_transport_issues_v6(issues, analysis_diagnostics)
    if analysis is not None:
        issues.extend(
            validate_analysis_v7(
                analysis,
                question=question,
                cards=cards,
                route=route,
            )
        )
    if analysis is None or issues:
        return {
            "text": fallback_v7(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "analysis",
            "issues": list(dict.fromkeys(issues)),
            "warnings": [],
            "ai_requests": 1,
            "analysis_diagnostics": analysis_diagnostics,
            "editor_diagnostics": None,
            "rejected_analysis": analysis,
        }

    editor_reply = editor_call(build_editor_prompt_v7(question, cards, route, analysis, topic))
    editor_raw, editor_diagnostics = unpack_reply_v6(editor_reply)
    final_payload, final_issues = parse_json_v6(editor_raw)
    final_issues = decorate_transport_issues_v6(final_issues, editor_diagnostics)
    warnings: list[str] = []
    rejected_text = None
    if final_payload is not None:
        if isinstance(final_payload.get("final_text"), str):
            normalized = normalize_final_layout_v6(final_payload["final_text"])
            final_payload = {**final_payload, "final_text": normalized}
            rejected_text = clean_stars_v6(normalized)
        hard_issues, warnings = validate_final_v7(
            final_payload,
            question=question,
            cards=cards,
        )
        final_issues.extend(hard_issues)

    if final_payload is None or final_issues:
        return {
            "text": fallback_v7(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "editor",
            "issues": list(dict.fromkeys(final_issues)),
            "warnings": warnings,
            "ai_requests": 2,
            "analysis": analysis,
            "analysis_diagnostics": analysis_diagnostics,
            "editor_diagnostics": editor_diagnostics,
            "rejected_text": rejected_text,
        }

    return {
        "text": clean_stars_v6(final_payload["final_text"]),
        "route": route,
        "used_fallback": False,
        "stage": "complete",
        "issues": [],
        "warnings": warnings,
        "ai_requests": 2,
        "analysis": analysis,
        "analysis_diagnostics": analysis_diagnostics,
        "editor_diagnostics": editor_diagnostics,
        "rejected_text": None,
    }


# Preview/tests use versioned names without importing V6 directly.
count_words_v7 = count_words_v6
split_paragraphs_v7 = split_paragraphs_v6
clean_stars_v7 = clean_stars_v6
