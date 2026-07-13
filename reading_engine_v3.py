"""Experimental one-call Reading Engine v3.7 for Moon Mentor.

The module is isolated from main.py and Reading Engine v2. It builds a compact
topic-aware prompt, makes exactly one AI call, and only removes Markdown
emphasis markers from the returned text.
"""

import re
from typing import Any, Callable


SPREAD_POSITIONS = {
    "daily_card": (
        "Фокус дня",
    ),
    "love": (
        "Что видно в контакте",
        "Центральное напряжение",
        "Практический ориентир",
    ),
    "career": (
        "Возможность",
        "Неясность или ограничение",
        "Условие решения",
    ),
    "personal_question": (
        "Центр вопроса",
        "Что важно увидеть",
        "На что опереться",
    ),
    "full": (
        "Центральная тема",
        "Что осложняет ситуацию",
        "Что поддерживает",
        "Куда направить внимание",
    ),
}


SPREAD_INSTRUCTIONS = {
    "daily_card": (
        "Дайте один символический фокус дня, одно возможное бытовое проявление "
        "и один вопрос для наблюдения. Не предсказывайте событие дня."
    ),
    "love": (
        "Перед ответом молча разделите известное и неизвестное. Известны только прямо "
        "описанные пользователем эпизоды и действия; причины, искренность, намерения и "
        "будущая устойчивость контакта неизвестны. Центральная мысль разбора — различие "
        "между качеством тёплых эпизодов и непрерывностью контакта. Свяжите карты вокруг "
        "этой мысли, а карту меры направьте на определение подходящего пользователю "
        "формата, не на ожидание или подстройку. В финале покажите один наблюдаемый "
        "аспект взаимности: самостоятельную инициативу, возобновление и поддержание связи."
    ),
    "career": (
        "Сохраните сильную логику карьерного разбора: сопоставьте привлекательность "
        "предложения с нехваткой ясности о самой работе. Не решайте за пользователя. "
        "Покажите, что оценить предложение помогают конкретные обязанности, полномочия, "
        "структура подчинения и ожидаемые результаты, желательно зафиксированные письменно. "
        "Не обещайте рост и не предполагайте, что роль получится сформировать после выхода."
    ),
    "personal_question": (
        "Сфокусируйтесь на одной дилемме пользователя. Если вопрос слишком широкий, "
        "не придумывайте сферу или обстоятельства: прямо назовите, какого контекста "
        "не хватает для индивидуального вывода."
    ),
    "full": (
        "Свяжите четыре позиции в последовательность: центральная тема, осложнение, "
        "опора и направление внимания. Не утверждайте, что случайный расклад описывает "
        "всю жизнь пользователя или гарантирует новый этап."
    ),
}


LOVE_STRUCTURE = """
Напишите три лёгких абзаца без заголовков:
1. Нейтрально отразите только описанные факты и назовите различие между теплом
   отдельных эпизодов и устойчивостью контакта.
2. Соберите сочетание в одну мысль, используя по имени не больше двух карт.
   Оставьте причины поведения другого человека неизвестными.
3. Назовите один наблюдаемый аспект взаимности без оценки и завершите одним
   мягким вопросом о подходящем пользователю формате контакта.

Общий объём — 110–145 слов. Не повторяйте одну мысль и не давайте указаний.
""".strip()


CAREER_STRUCTURE = """
Напишите три естественных абзаца без заголовков:
1. Покажите конфликт между привлекательностью предложения и неясностью условий.
2. Свяжите символику карт с обязанностями, полномочиями и структурой роли.
3. Назовите конкретную информацию, которая поможет пользователю самому оценить
   предложение, и завершите одним точным вопросом о его приоритетах.

Общий объём — 130–170 слов. Не выносите решение за пользователя.
""".strip()


MULTI_CARD_STRUCTURE = """
Напишите три естественных абзаца без заголовков:
1. Ясно назовите главный рисунок ситуации и напряжение выбора, не давая вердикта.
2. Свяжите карты с конкретным вопросом в одну мысль.
3. Покажите, какой факт или наблюдение может добавить ясности, и завершите одним
   мягким, точным вопросом для самостоятельного решения.

Общий объём — 130–170 слов. Не растягивайте мысль ради объёма.
""".strip()

DAILY_STRUCTURE = """
Напишите три коротких абзаца без заголовков:
1. Центральная символическая тема карты.
2. Одно возможное бытовое проявление без предсказания.
3. Один небольшой ориентир и один вопрос для наблюдения.

Общий объём — 90–130 слов.
""".strip()


def prepare_cards_v3(
    cards: list[dict[str, Any]],
    spread_type: str,
    topic: str = "general",
) -> list[dict[str, str]]:
    """Keep only the card data needed by the compact v3 prompt."""
    positions = SPREAD_POSITIONS.get(
        spread_type,
        SPREAD_POSITIONS["personal_question"],
    )
    prepared: list[dict[str, str]] = []

    for index, card in enumerate(cards):
        position = (
            positions[index]
            if index < len(positions)
            else f"Дополнительный акцент {index + 1}"
        )
        prepared.append(
            {
                "position": position,
                "name": card["name"],
                "meaning": card.get(topic, card.get("general", "")),
            }
        )

    return prepared


def format_cards_v3(cards: list[dict[str, str]]) -> str:
    """Format cards as compact source material, not ready-made paragraphs."""
    return "\n".join(
        f"- {card['position']}: {card['name']} — {card['meaning']}"
        for card in cards
    )


def build_reading_v3_prompt(
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    topic: str = "general",
) -> str:
    """Build a concise topic-aware prompt for a single AI request."""
    cards_text = format_cards_v3(prepare_cards_v3(cards, spread_type, topic))
    spread_instruction = SPREAD_INSTRUCTIONS.get(
        spread_type,
        SPREAD_INSTRUCTIONS["personal_question"],
    )
    output_structure = {
        "daily_card": DAILY_STRUCTURE,
        "love": LOVE_STRUCTURE,
        "career": CAREER_STRUCTURE,
    }.get(spread_type, MULTI_CARD_STRUCTURE)

    return f"""
Ты — Moon Mentor. Напиши лёгкий, цельный символический разбор Таро на русском.

Тип расклада: {spread_type}
Тема: {topic}
Вопрос пользователя: {user_question}

Фактами о ситуации считай только слова пользователя:
{user_question}

Карты, позиции и символические значения:
{cards_text}

Фокус этого расклада:
{spread_instruction}

Правила:
- Сразу откликнись на конкретный вопрос, но не решай за человека.
- Обращайся к пользователю только на «вы»; не переходи на «ты».
- Не давай вердиктов «стоит», «не стоит», «соглашайтесь», «откажитесь»,
  «продолжайте» или «прекратите».
- Для вопроса «да или нет» покажи главное напряжение выбора и недостающий факт.
- Сначала найди общий рисунок сочетания; не пересказывай карты по очереди.
- Названия карт используй как символические опоры, а не доказательства фактов.
- В обычном раскладе назови не больше двух карт; влияние остальных включи в общий смысл.
- Не приписывай пользователю или другому человеку мысли, чувства, желания,
  намерения, характер, готовность или скрытые причины.
- Не усиливай слова пользователя и не превращай нехватку информации в тайну.
- Не предсказывай исход и не обещай успех, возвращение или изменение.
- Предложи способ добавить ясности, но не указывай, какое решение принять.
- Не придумывай доступные пользователю действия или договорённости.
- Не используй в готовом тексте служебные выражения «центральная дилемма»,
  «наблюдаемый критерий», «условие решения» и «практический ориентир».
- Избегай канцелярита, абстрактных усилителей и повторов. Пиши короткими фразами,
  тепло и естественно, без эзотерического пафоса.
- Не используй Markdown-звёздочки.
- Верни только готовый расклад.

Формат:
{output_structure}
""".strip()

def clean_reading_v3_answer(answer: str) -> str:
    """Remove only paired Markdown emphasis stars without rewriting text."""
    cleaned = re.sub(r"\*\*(?=\S)([^*\n]*?\S)\*\*", r"\1", answer)
    cleaned = re.sub(
        r"(?<!\*)\*(?=\S)([^*\n]*?\S)\*(?!\*)",
        r"\1",
        cleaned,
    )
    return cleaned


def inspect_reading_v3_answer(
    answer: str,
    spread_type: str,
    card_names: list[str] | None = None,
) -> dict[str, Any]:
    """Report format deviations without changing or regenerating the answer."""
    words = len(
        re.findall(
            r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?",
            answer,
        )
    )
    paragraphs = [part for part in re.split(r"\n\s*\n", answer) if part.strip()]
    min_words, max_words = (
        (90, 130)
        if spread_type == "daily_card"
        else ((110, 145) if spread_type == "love" else (130, 170))
    )
    issues: list[str] = []
    if not min_words <= words <= max_words:
        issues.append(f"word_count:{words}")
    expected_paragraphs = 3
    if len(paragraphs) != expected_paragraphs:
        issues.append(f"paragraph_count:{len(paragraphs)}")
    if re.search(r"\b(?:ты|твой|твоя|твои|тебе|тебя)\b", answer, re.IGNORECASE):
        issues.append("informal_address")
    named_cards = []
    if card_names:
        named_cards = [
            name for name in card_names
            if re.search(rf"(?<!\\w){re.escape(name)}(?!\\w)", answer, re.IGNORECASE)
        ]
    if spread_type == "love" and len(named_cards) > 2:
        issues.append(f"named_cards:{len(named_cards)}")
    return {
        "word_count": words,
        "paragraph_count": len(paragraphs),
        "within_word_target": min_words <= words <= max_words,
        "has_expected_paragraphs": len(paragraphs) == expected_paragraphs,
        "named_card_count": len(named_cards),
        "issues": issues,
    }


def generate_reading_v3(
    *,
    spread_type: str,
    user_question: str,
    cards: list[dict[str, Any]],
    ai_call: Callable[[str], str | None],
    topic: str = "general",
) -> str:
    """Make exactly one AI call and apply non-generative local cleanup."""
    prompt = build_reading_v3_prompt(
        spread_type=spread_type,
        user_question=user_question,
        cards=cards,
        topic=topic,
    )
    answer = ai_call(prompt)
    if not answer:
        return ""
    return clean_reading_v3_answer(answer)
