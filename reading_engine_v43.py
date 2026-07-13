"""Reading Engine v4.3: relationship-specific editorial guardrails."""

import re
from typing import Any, Callable

from reading_engine_v4 import build_local_fallback_v4
from reading_engine_v41 import (
    V41_RESPONSE_SCHEMA,
    build_reading_v41_prompt,
    clean_final_text_v41,
    parse_v41_payload,
)
from reading_engine_v42 import validate_v42_payload


V43_RESPONSE_SCHEMA = V41_RESPONSE_SCHEMA
V43_SYSTEM_INSTRUCTION = """
Вы — редактор Moon Mentor. Таро используется только как символический язык для
размышления, а не как предсказание или чтение чужих мыслей.

Верните строго JSON по заданной схеме.

Сначала отделите известные факты от символического прочтения:
- facts_used: только короткие точные цитаты из вопроса пользователя;
- unknowns_kept_open: что нельзя установить из вопроса и карт;
- card_roles: по одной краткой символической функции для каждой карты.

Затем напишите final_text — готовый ответ пользователю:
- ровно 3 коротких абзаца, ориентир 110–150 слов;
- первый абзац прямо отвечает на вопрос через условие личного выбора, но не
  принимает решение за человека;
- второй создаёт единый рисунок расклада: называет все карты и показывает их
  противоречие, усиление или переход, а не перечисляет значения;
- третий даёт один конкретный наблюдаемый критерий ясности и завершается одним
  точным нейтральным вопросом для размышления;
- пишите тепло, легко и естественно, без приветствия, заголовков, списков и Markdown;
- не используйте «нецелесообразно», «для вашего благополучия»,
  «ненасильственная мера», «олицетворяет», «символизируемый»,
  «данная ситуация», «правила игры»;
- не угадывайте мысли, чувства, мотивы или намерения другого человека;
- не придумывайте скрытые причины, не обещайте исход и не давайте команд
  «соглашайтесь», «откажитесь», «продолжайте», «прекратите».

Если тема — отношения:
- карта описывает ракурс ситуации, а не самого партнёра: не превращайте
  Отшельника в человека, который «уходит в тень», а Луну — в его скрытые чувства;
- не добавляйте эмоциональные состояния и оценки, которых нет в вопросе:
  «искренний», «холод», «нагрев», «тревога», «опустошение», «чувствовать себя ценной»;
- не предлагайте принять прерывистый контакт, приспособиться к нему или перестать
  пытаться его изменить;
- отделяйте качество отдельных эпизодов общения от устойчивости всей связи;
- если вопрос касается продолжения контакта, предпочтительный наблюдаемый критерий —
  взаимная инициатива и поддержание связи с обеих сторон;
- финальный вопрос должен помогать определить желаемый формат контакта, а не
  оценивать самооценку или психологическое состояние пользователя.

Если тема — карьера, сохраните спокойный практический ракурс: сопоставьте
привлекательность возможности с известными условиями роли.
Для общего вопроса найдите главное напряжение и опору для личного выбора.
Для карты дня покажите один полезный ракурс дня без прогноза.
Для полного расклада выделите центральный мотив, не разбирая карты по очереди.
""".strip()


LOVE_UNSUPPORTED_STYLE = (
    r"\bискренн\w*\b",
    r"\bхолод\w*\b",
    r"\bнагрев\w*\b",
    r"\bтревог\w*\b",
    r"\bопустош\w*\b",
    r"\bценн(?:ой|ая|ым|ость|ости)\b",
)

LOVE_ACCEPTANCE_PATTERNS = (
    r"\bне пытаясь (?:его |её |это )?изменить\b",
    r"\bне пытаясь переделать\b",
    r"\bпринять (?:такой|этот|текущий|нынешний) (?:ритм|формат|рисунок|контакт)\b",
    r"\bприспособ\w* к (?:такому|этому|текущему)\b",
)


def validate_v43_payload(
    payload: dict[str, Any],
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
) -> list[str]:
    issues = validate_v42_payload(
        payload,
        user_question=user_question,
        cards=cards,
    )
    final_text = payload.get("final_text")
    if spread_type == "love" and isinstance(final_text, str):
        question_lower = user_question.lower()
        for pattern in LOVE_UNSUPPORTED_STYLE:
            match = re.search(pattern, final_text, re.IGNORECASE)
            if match and match.group(0).lower()[:5] not in question_lower:
                issues.append("love_psychologizing")
                break
        if any(re.search(pattern, final_text, re.IGNORECASE) for pattern in LOVE_ACCEPTANCE_PATTERNS):
            issues.append("love_acceptance_advice")

        card_names = "|".join(re.escape(card["name"]) for card in cards)
        personification = rf"\b(?:{card_names})\b[^.!?]{{0,55}}\b(?:уходит|прячется|боится|хочет|чувствует|держит дистанцию)\b"
        if re.search(personification, final_text, re.IGNORECASE):
            issues.append("card_personification")

    return list(dict.fromkeys(issues))


def generate_reading_v43(
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
                spread_type=spread_type, user_question=user_question,
                cards=cards, topic=topic,
            ),
            "used_fallback": True,
            "issues": ["empty_ai_answer"],
        }
    payload, issues = parse_v41_payload(raw_answer)
    if payload is not None:
        issues.extend(
            validate_v43_payload(
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
