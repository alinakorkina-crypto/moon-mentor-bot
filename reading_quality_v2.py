"""Quality checks and targeted repair for Reading Engine v2.

The module is isolated from the Telegram bot. It detects a small set of
high-confidence quality problems and builds a repair prompt only when needed.
"""

import re
from typing import Any


RISK_PATTERNS = {
    "hidden_reason": (
        r"потребност[ьи] в (?:личном|собственном) пространстве",
        r"ему нужно (?:побыть|разобраться|подумать|принять)",
        r"он (?:боится|хочет|не хочет|чувствует|думает|планирует)",
        r"она (?:боится|хочет|не хочет|чувствует|думает|планирует)",
        r"естественн(?:ая|ой|ую) часть (?:его|ее|её) ритма",
    ),
    "unsupported_certainty": (
        r"(?:карта|карты|расклад) (?:ясно |точно |ярко )?подтвержда",
        r"(?:это|эти моменты) не (?:иллюзия|видимость)",
        r"(?:искреннее|подлинное) тепло",
        r"(?:действительно|несомненно) (?:наполнен|является|существует)",
    ),
    "markdown_emphasis": (
        r"**[^*]+**",
        r"(?<!*)*[^*]+*(?!*)",
    ),
}


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?", text))


def detect_quality_issues(
    text: str,
    *,
    max_words: int = 260,
) -> list[dict[str, Any]]:
    """Return high-confidence issues without destructively editing the answer."""
    issues: list[dict[str, Any]] = []

    for issue_type, patterns in RISK_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                issues.append(
                    {
                        "type": issue_type,
                        "excerpt": match.group(0),
                        "instruction": {
                            "hidden_reason": (
                                "Уберите объяснение мыслей, чувств, потребностей или "
                                "причин поведения другого человека. Оставьте только "
                                "наблюдаемое действие из вопроса пользователя."
                            ),
                            "unsupported_certainty": (
                                "Не представляйте карту как доказательство факта. "
                                "Отнесите факт к словам пользователя, а символику карты "
                                "сформулируйте как возможный ракурс."
                            ),
                            "markdown_emphasis": (
                                "Удалите Markdown-звёздочки, сохранив обычный текст."
                            ),
                        }[issue_type],
                    }
                )
                break

    words = count_words(text)
    if words > max_words:
        issues.append(
            {
                "type": "too_long",
                "excerpt": f"{words} слов при максимуме {max_words}",
                "instruction": (
                    "Сократите ответ до установленного объёма: уберите повторы, "
                    "вводные фразы и повторное перечисление значений карт."
                ),
            }
        )

    return issues


def build_repair_prompt(
    original_answer: str,
    issues: list[dict[str, Any]],
    *,
    user_question: str,
    max_words: int = 260,
) -> str:
    """Build a narrowly scoped rewrite request for an already generated answer."""
    issue_lines = "
".join(
        f"- {item['type']}: {item['instruction']} "
        f"Проблемный фрагмент: «{item['excerpt']}»."
        for item in issues
    )

    return f"""
Ты — редактор Moon Mentor. Перепиши готовый расклад, исправив только перечисленные
нарушения. Сохрани прямой ответ, полезные выводы, названия карт и общий смысл.

ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{user_question}

НАРУШЕНИЯ:
{issue_lines}

ИСХОДНЫЙ ОТВЕТ:
{original_answer}

ПРАВИЛА РЕМОНТА:
- Фактами считаются только сведения из вопроса пользователя.
- Карты дают символический ракурс, но ничего не доказывают.
- Не объясняй причины поведения, мысли, чувства и потребности другого человека.
- Не добавляй новых фактов или новых трактовок.
- Каждый вывод сформулируй один раз.
- Не используй Markdown-звёздочки.
- Объём не более {max_words} слов.
- Верни только исправленный расклад без комментариев редактора.
""".strip()


def repair_answer_if_needed(
    answer: str,
    *,
    user_question: str,
    ai_call,
    max_words: int = 260,
) -> tuple[str, list[dict[str, Any]], bool]:
    """Run one repair call only when deterministic checks find an issue."""
    issues = detect_quality_issues(answer, max_words=max_words)
    if not issues:
        return answer, [], False

    repaired = ai_call(
        build_repair_prompt(
            answer,
            issues,
            user_question=user_question,
            max_words=max_words,
        )
    )
    if not repaired:
        return answer, issues, False

    return repaired.strip(), issues, True
