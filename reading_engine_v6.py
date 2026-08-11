"""Reading Engine v6 MVP for initiative and personal-choice questions."""

import json
import re
import unicodedata
from typing import Any, Callable


ROUTE_CONFIG_V6 = {
    "initiative": {
        "positions": (
            "Какой импульс или ожидание связано с возможностью контакта",
            "Что делает эту возможность неясной или противоречивой",
            "На какой внутренний или проверяемый ориентир переносится фокус",
        ),
        "tendencies": (
            "symbolic_support",
            "weak_symbolic_support",
            "contradictory",
            "unsupported",
        ),
        "tendency_descriptions": {
            "symbolic_support": "сочетание символически поддерживает возможность инициативы без гарантии события",
            "weak_symbolic_support": "символическая поддержка инициативы слабая и недостаточна для уверенного ожидания",
            "contradictory": "сочетание даёт противоречивую картину без надёжного подтверждения",
            "unsupported": "сочетание не даёт символической опоры рассчитывать на инициативу",
        },
        "answer_rule": (
            "Ответьте, насколько сочетание символически поддерживает возможность "
            "самостоятельной инициативы: поддерживает, поддерживает слабо, даёт "
            "противоречивую картину или не даёт опоры для такого ожидания. Это оценка "
            "символического рисунка, а не прогноз чужого действия."
        ),
        "editor_rule": (
            "Психологический фокус — не угадывать действие другого человека, а показать, "
            "какое место в вопросе занимает ожидание и что пользователь считает реальным "
            "проявлением инициативы. Не подменяйте ответ общим советом переключиться на себя."
        ),
        "focuses": {
            "evidence_threshold": "что именно считать реальным проявлением инициативы",
            "waiting_cost": "сколько внимания занимает ожидание без подтверждения",
            "uncertainty_limit": "где проходит личная граница неопределённости",
            "personal_agency": "что остаётся в зоне собственного выбора пользователя",
        },
        "criteria": {
            "independent_contact": "самостоятельное сообщение или звонок без предварительного шага пользователя",
            "sustained_conversation": "самостоятельное содержательное продолжение разговора",
            "concrete_invitation": "конкретное предложение встретиться или поговорить",
            "repeated_initiative": "инициатива проявляется больше одного раза",
        },
    },
    "personal_choice": {
        "positions": (
            "Что делает рассматриваемый вариант привлекательным или значимым",
            "Главное противоречие, цена или ограничение этого варианта",
            "Какой критерий помогает пользователю определить собственную позицию",
        ),
        "tendencies": ("fits_conditions", "conflicts_conditions", "conditional", "open"),
        "tendency_descriptions": {
            "fits_conditions": "вариант символически согласуется с обозначенными условиями пользователя",
            "conflicts_conditions": "вариант входит в заметное противоречие с обозначенными условиями",
            "conditional": "ценность варианта зависит от проверяемого условия",
            "open": "данных недостаточно, и выбор остаётся открытым",
        },
        "answer_rule": (
            "Не принимайте решение за пользователя. Покажите, склоняется ли символический "
            "рисунок к варианту, отдаляется от него или делает решение условным."
        ),
        "editor_rule": (
            "Если вопрос касается отношений, не предлагайте пользователю терпеть, принимать "
            "или спокойно переносить неудобную динамику. Не делайте его ответственным за "
            "устойчивость контакта. Основной проверяемый критерий — свойства самой связи: "
            "взаимность, инициатива, регулярность или соблюдение обозначенных границ."
        ),
        "focuses": {
            "needs_fit": "соответствует ли вариант потребностям и ожиданиям пользователя",
            "reciprocity": "есть ли взаимность в наблюдаемой динамике",
            "boundary": "какое условие или граница важны для выбора",
            "tradeoff": "как соотносятся ценность варианта и его цена",
            "decision_conditions": "какие проверяемые условия нужны для решения",
            "clarity_requirements": "какой конкретики не хватает для выбора",
        },
        "criteria": {
            "mutual_initiative": "инициатива и поддержание связи происходят с обеих сторон",
            "consistency": "наблюдаемая регулярность и устойчивость контакта",
            "boundary_response": "реакция другой стороны на прямо обозначенное условие или границу",
            "clear_conditions": "понятные и зафиксированные условия рассматриваемого варианта",
            "concrete_information": "конкретная информация, которой не хватает для решения",
        },
        "topic_profiles": {
            "love": {
                "focus_codes": ("needs_fit", "reciprocity", "boundary", "tradeoff"),
                "criterion_codes": (
                    "mutual_initiative",
                    "consistency",
                    "boundary_response",
                ),
                "editor_rule": (
                    "Описывайте свойства контакта живым языком: взаимность, устойчивость, "
                    "инициативу и реакцию на границы. Не переносите в отношения лексику "
                    "договоров, зафиксированных условий или рассматриваемых вариантов."
                ),
            },
            "career": {
                "focus_codes": (
                    "needs_fit",
                    "tradeoff",
                    "decision_conditions",
                    "clarity_requirements",
                ),
                "criterion_codes": ("clear_conditions", "concrete_information"),
                "editor_rule": (
                    "Связывайте выбор с проверяемой конкретикой роли: обязанностями, "
                    "полномочиями, подчинением и критериями результата."
                ),
            },
            "general": {
                "focus_codes": (
                    "needs_fit",
                    "boundary",
                    "tradeoff",
                    "decision_conditions",
                    "clarity_requirements",
                ),
                "criterion_codes": (
                    "boundary_response",
                    "clear_conditions",
                    "concrete_information",
                ),
                "editor_rule": "Сохраняйте нейтральный язык, соответствующий вопросу.",
            },
        },
    },
}


INTERACTION_CODES_V6 = {
    "contrast": "карты подчёркивают разные стороны или разнонаправленные силы",
    "restriction": "одна тема заметно ограничивает или ослабляет другую",
    "reinforcement": "темы карт усиливают один общий мотив",
    "correction": "одна карта уточняет и меняет способ чтения остальных",
}


ANALYSIS_SYSTEM_V6 = """
Вы — маршрутизатор анализа Moon Mentor. Не пишите толкование и не создавайте
психологическую версию. Верните только короткий JSON-план по заданной схеме.

- question_quotes: 1–3 точные непрерывные цитаты из вопроса;
- interaction_code, focus_code, tendency_code и criterion_code выбирайте только
  из разрешённых значений, переданных в запросе;
- порядок карт — аналитические ракурсы, а не хронология событий;
- коды описывают способ чтения, но не будущее, мысли или мотивы другого человека;
- никаких дополнительных полей и свободных объяснений.
""".strip()


EDITOR_SYSTEM_V6 = """
Вы — редактор Moon Mentor. Получите вопрос, карты, маршрут, проверенный анализ и
эталон нужного тона. Верните строго JSON с полем final_text.

final_text:
- ровно 3 коротких абзаца, 110–150 слов;
- первый абзац сразу отвечает на исходный вопрос через степень символической
  поддержки или условие личного выбора, не выдавая прогноз и не уходя от ответа;
- достаточно один раз обозначить, что речь идёт о символике расклада;
- второй абзац называет все карты и объясняет их взаимодействие, не перечисляя
  три словарных значения и не превращая порядок карт в хронологию событий;
- третий абзац содержит один наблюдаемый критерий и один вопрос в конце;
- психологический фокус направлен на отношение пользователя к неопределённости,
  ожиданию, границам или условиям выбора только там, где это следует из вопроса;
- используйте только точные цитаты вопроса, описания выбранных кодов и переданные
  Python значения карт. Не добавляйте собственную психологическую версию;
- нельзя ставить пользователю психологический диагноз или объявлять скрытый мотив;
- допустима живая условная версия: «это может указывать», «в символике расклада»;
- нельзя утверждать чужие мысли, чувства, мотивы, намерения, сроки или будущие
  действия как факты;
- нельзя придумывать произошедшие события и скрытые причины;
- нельзя давать команды и манипулятивные советы, как спровоцировать другого;
- без приветствия, заголовков, списков, Markdown, канцелярита, эзотерического
  пафоса и повторяющихся предостережений.
""".strip()


ANALYSIS_SCHEMA_V6 = {
    "type": "object",
    "properties": {
        "question_route": {"type": "string"},
        "question_quotes": {"type": "array", "items": {"type": "string"}},
        "interaction_code": {"type": "string"},
        "focus_code": {"type": "string"},
        "tendency_code": {"type": "string"},
        "criterion_code": {"type": "string"},
    },
    "required": [
        "question_route",
        "question_quotes",
        "interaction_code",
        "focus_code",
        "tendency_code",
        "criterion_code",
    ],
}


EDITOR_SCHEMA_V6 = {
    "type": "object",
    "properties": {"final_text": {"type": "string"}},
    "required": ["final_text"],
}


STYLE_EXAMPLES_V6 = {
    "initiative": """
Вопрос: «Проявится ли человек сам?»
Карты: Маг — Повешенный — Суд

По символике сочетания возможность инициативы поддержана, но слабо: карты не дают
достаточной опоры рассчитывать на самостоятельный первый шаг. Вопрос остаётся не
о точном будущем, а о том, сколько значения сейчас получает само ожидание контакта.

Маг усиливает тему проявления, Повешенный ограничивает её свободное развитие, а
Суд возвращает к незавершённой теме. Вместе карты показывают не готовое событие,
а противоречие между возможностью действовать и сохраняющейся паузой.

Наблюдаемым подтверждением станет самостоятельное продолжение разговора, а не
случайная реакция. Какое действие вы сочтёте настоящим шагом и сколько готовы
оставаться в ожидании без него?
""".strip(),
    "personal_choice_career": """
Вопрос: «Стоит ли принимать предложение о новой работе?»
Карты: Колесо Фортуны — Луна — Император

По символике расклада решение выглядит условным: возможность перемен заметна,
но её ценность зависит от того, удастся ли сделать условия достаточно ясными.

Колесо Фортуны подчёркивает привлекательность нового поворота, Луна добавляет
неопределённость, а Император связывает выбор с конкретной структурой роли.
Поэтому главный вопрос не в самой перемене, а в том, на что она будет опираться.

Критерием станет ясность обязанностей, полномочий и ожидаемых результатов. Какая
информация необходима вам, чтобы принять это решение без догадок?
""".strip(),
    "personal_choice_love": """
Вопрос: «Мне хорошо с человеком, но общение держится в основном на моей
инициативе. Стоит ли продолжать?»
Карты: Двойка Кубков — Повешенный — Правосудие

По символике расклада решение выглядит условным: ценность контакта заметна, но
его продолжение стоит оценивать вместе с тем, насколько взаимно поддерживается связь.

Двойка Кубков подчёркивает привлекательность близости, Повешенный добавляет
зависание и неравномерность, а Правосудие переводит их сочетание в вопрос баланса.
Вместе карты отделяют приятные моменты от устойчивости самого контакта.

Критерием станет то, возникает ли инициатива с обеих сторон без постоянного
подталкивания. Какой уровень взаимности необходим вам, чтобы эта связь имела ценность?
""".strip(),
    "personal_choice_general": """
Вопрос: «Стоит ли соглашаться на предложение, если мне пока не хватает информации?»
Карты: Шут — Луна — Правосудие

По символике расклада решение остаётся условным: новая возможность заметна, но
её ценность зависит от информации, которую ещё можно проверить.

Шут показывает привлекательность нового шага, Луна подчёркивает недостаток
ясности, а Правосудие возвращает выбор к понятному критерию. Вместе карты не
решают за человека, а отделяют интерес к варианту от его реальных условий.

Ориентиром станет конкретный ответ на главный открытый вопрос. Какой информации
вам не хватает, чтобы оценить этот вариант без догадок?
""".strip(),
}


HIGH_RISK_PATTERNS_V6 = (
    r"\b(?:он|она|человек)\s+(?:точно\s+|обязательно\s+|скоро\s+)?"
    r"(?:не\s+)?(?:выйдет|напишет|позвонит|верн[её]тся|проявится)\b",
    r"\b(?:он|она)\s+(?:хочет|боится|чувствует|думает|решил[аи]?|планирует)\b",
    r"\b(?:вам|тебе)\s+(?:нужно|необходимо|следует|стоит)\b",
    r"\b(?:ждите|напишите|позвоните|прекратите|продолжайте|соглашайтесь)\b",
)


SAFE_PREDICTION_PREFIX_PATTERNS_V6 = (
    r"\bне\s+(?:гарантирует|означает|подтверждает|показывает|доказывает)"
    r"(?:\s+\w+){0,3}\s*,?\s+что(?:\s+\w+){0,3}\s*$",
    r"\bнет(?:\s+\w+){0,3}\s+основани\w*\s+"
    r"(?:считать|утверждать|ожидать)\s*,?\s+что(?:\s+\w+){0,3}\s*$",
    r"\bнельзя\s+(?:считать|утверждать)\s*,?\s+что(?:\s+\w+){0,3}\s*$",
)


UNSUPPORTED_STORY_PATTERNS_V6 = (
    r"\bв ближайшее время\b",
    r"\bвнезапн\w*\b",
    r"\bнеожиданн\w*\b",
    r"\bразруш\w* привычн\w* формат\w*\b",
    r"\bэнерги\w* взаимодействи\w*\b",
    r"\bкрасив\w* дистанци\w*\b",
    r"\bдолгосрочн\w* надежд\w*\b",
    r"\bнеизбежн\w*\b",
    r"\bбуд\w* (?:чередоваться|повторяться|пропадать|возникать)\b",
    r"\bперестан\w*\s+приносить\s+дискомфорт\w*\b",
)


LOVE_DOMAIN_LEAK_PATTERNS_V6 = (
    r"\bзафиксированн\w*\s+услови\w*\b",
    r"\bрассматриваем\w*\s+вариант\w*\s+общен\w*\b",
)


PSEUDO_PSYCHOLOGY_PATTERNS_V6 = (
    r"\bу вас (?:травма|зависимость|контрзависимость)\b",
    r"\bу вас \w+ привязанность\b",
    r"\bвы (?:эмоционально зависимы|одержимы|созависимы)\b",
    r"\bваше бессознательное\b",
)


ADAPTATION_AND_BLAME_PATTERNS_V6 = (
    r"\bесли (?:вы|ты) готов\w* (?:принять|терпеть|переносить|адаптироваться)\b",
    r"\b(?:принять|терпеть) (?:такой|этот|прерывистый|неудобный)\w* "
    r"(?:ритм|формат|контакт|динамик)\w*\b",
    r"\bстабильност\w+ (?:этого |вашего |их )?(?:союза|контакта|отношений)\w* "
    r"зависит от (?:вашего|твоего)\b",
    r"\bпереключ\w*(?:\s+\w+){0,5}\s+(?:дела|задачи|задачах)\b",
)


UNSUPPORTED_INFERENCE_PATTERNS_V6 = (
    ("internal_barriers", r"\bвнутренн\w*\s+барьер\w*\b"),
    ("idealization", r"\bидеализ\w*\b"),
    ("long_term_perspective", r"\bдолгосрочн\w*\s+перспектив\w*\b"),
    ("exhausting_anxiety", r"\bистощающ\w*\s+тревог\w*\b"),
    ("psychological_center", r"\bпсихологическ\w*\s+центр\w*\b"),
    ("waiting_costs", r"\bзатрат\w*\s+на\s+ожидан\w*\b"),
    ("rare_moments", r"\bредк\w*\s+момент\w*\b"),
    ("destructive_influence", r"\bразрушительн\w*\s+влиян\w*\b"),
    ("near_term_claim", r"\bскор(?:ой|ого|ому|ую|ым|ом)\s+(?:инициатив|контакт|шаг)\w*\b"),
)


RELATIONSHIP_QUESTION_MARKERS_V6 = (
    "отношен",
    "контакт",
    "общен",
    "связь",
    "встреч",
)


RELATIONSHIP_CRITERION_MARKERS_V6 = (
    "взаимн",
    "инициатив",
    "с обеих сторон",
    "регулярн",
    "частот",
    "длительност",
    "границ",
)


INITIATIVE_CRITERION_MARKERS_V6 = (
    "сообщен",
    "звон",
    "инициатив",
    "самостоятельн",
    "продолжен",
    "действ",
)


LATIN_TO_CYRILLIC_LOOKALIKES_V6 = str.maketrans(
    {
        "A": "А", "a": "а", "B": "В", "C": "С", "c": "с",
        "E": "Е", "e": "е", "H": "Н", "K": "К", "k": "к",
        "M": "М", "O": "О", "o": "о", "P": "Р", "p": "р",
        "T": "Т", "X": "Х", "x": "х", "Y": "У", "y": "у",
    }
)


def normalize_text_v6(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().replace("ё", "е"))


def normalize_topic_v6(topic: str) -> str:
    normalized = normalize_text_v6(topic)
    if normalized in {"love", "relationship", "relationships", "отношения"}:
        return "love"
    if normalized in {"career", "work", "job", "карьера", "работа"}:
        return "career"
    return "general"


def route_topic_profile_v6(route: str, topic: str) -> dict[str, Any]:
    config = ROUTE_CONFIG_V6[route]
    profiles = config.get("topic_profiles")
    if not profiles:
        return {
            "focus_codes": tuple(config["focuses"]),
            "criterion_codes": tuple(config["criteria"]),
            "editor_rule": "",
        }
    return profiles[normalize_topic_v6(topic)]


def style_example_v6(route: str, topic: str) -> str:
    if route == "initiative":
        return STYLE_EXAMPLES_V6["initiative"]
    return STYLE_EXAMPLES_V6[f"personal_choice_{normalize_topic_v6(topic)}"]


def source_corpus_v6(question: str, cards: list[dict[str, Any]]) -> str:
    card_text = " ".join(
        value
        for card in cards
        for value in card.values()
        if isinstance(value, str)
    )
    return normalize_text_v6(question + " " + card_text)


def unsupported_inference_markers_v6(
    text: str,
    *,
    question: str,
    cards: list[dict[str, Any]],
) -> list[str]:
    normalized = normalize_text_v6(text)
    sources = source_corpus_v6(question, cards)
    return [
        label
        for label, pattern in UNSUPPORTED_INFERENCE_PATTERNS_V6
        if re.search(pattern, normalized) and not re.search(pattern, sources)
    ]


def has_safe_prediction_prefix_v6(text: str, match_start: int) -> bool:
    sentence_start = max(
        text.rfind(".", 0, match_start),
        text.rfind("!", 0, match_start),
        text.rfind("?", 0, match_start),
        text.rfind("\n", 0, match_start),
    )
    prefix = text[sentence_start + 1:match_start]
    return any(
        re.search(pattern, prefix, re.IGNORECASE)
        for pattern in SAFE_PREDICTION_PREFIX_PATTERNS_V6
    )


def has_high_risk_claim_v6(text: str) -> bool:
    for index, pattern in enumerate(HIGH_RISK_PATTERNS_V6):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if index < 2 and has_safe_prediction_prefix_v6(text, match.start()):
                continue
            return True
    return False


def infer_question_route_v6(question: str) -> str:
    q = normalize_text_v6(question)
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


def prepare_cards_v6(
    cards: list[dict[str, Any]],
    route: str,
    topic: str = "general",
) -> list[dict[str, str]]:
    positions = ROUTE_CONFIG_V6[route]["positions"]
    normalized_topic = normalize_topic_v6(topic)
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


def build_analysis_prompt_v6(
    question: str,
    cards: list[dict[str, Any]],
    route: str,
    topic: str = "general",
) -> str:
    config = ROUTE_CONFIG_V6[route]
    topic_profile = route_topic_profile_v6(route, topic)
    prepared = prepare_cards_v6(cards, route, topic)
    card_block = "\n".join(
        f"- {item['position']}: {item['name']} — {item['meaning']}"
        for item in prepared
    )
    tendencies = ", ".join(config["tendencies"])
    interaction_options = "\n".join(
        f"- {code}: {description}"
        for code, description in INTERACTION_CODES_V6.items()
    )
    focus_options = "\n".join(
        f"- {code}: {description}"
        for code, description in config["focuses"].items()
        if code in topic_profile["focus_codes"]
    )
    criterion_options = "\n".join(
        f"- {code}: {description}"
        for code, description in config["criteria"].items()
        if code in topic_profile["criterion_codes"]
    )
    return f"""
Маршрут вопроса: {route}
Тема вопроса: {normalize_topic_v6(topic)}
Вопрос пользователя:
{question}

Карты, аналитические позиции и допустимые символические темы:
{card_block}

Допустимые tendency_code: {tendencies}

Допустимые interaction_code:
{interaction_options}

Допустимые focus_code:
{focus_options}

Допустимые criterion_code:
{criterion_options}

Порядок карт не является временной последовательностью. Не превращайте позиции
в рассказ «сначала это случилось, потом произошло другое».
Верните только JSON.
""".strip()


def build_editor_prompt_v6(
    question: str,
    cards: list[dict[str, Any]],
    route: str,
    analysis: dict[str, Any],
    topic: str = "general",
) -> str:
    config = ROUTE_CONFIG_V6[route]
    topic_profile = route_topic_profile_v6(route, topic)
    verified_plan = {
        "question_quotes": analysis["question_quotes"],
        "interaction": {
            "code": analysis["interaction_code"],
            "description": INTERACTION_CODES_V6[analysis["interaction_code"]],
        },
        "psychological_focus": {
            "code": analysis["focus_code"],
            "description": config["focuses"][analysis["focus_code"]],
        },
        "symbolic_tendency": {
            "code": analysis["tendency_code"],
            "description": config["tendency_descriptions"][analysis["tendency_code"]],
        },
        "observable_criterion": {
            "code": analysis["criterion_code"],
            "description": config["criteria"][analysis["criterion_code"]],
        },
        "cards": prepare_cards_v6(cards, route, topic),
    }
    return f"""
Маршрут: {route}
Правило ответа для маршрута:
{ROUTE_CONFIG_V6[route]['answer_rule']}

Редакторское правило для маршрута:
{ROUTE_CONFIG_V6[route]['editor_rule']}

Редакторское правило для темы:
{topic_profile['editor_rule']}

Вопрос:
{question}

Проверенный план и единственные допустимые источники:
{json.dumps(verified_plan, ensure_ascii=False, indent=2)}

Эталон тона и логики для этого маршрута:
{style_example_v6(route, topic)}

Не копируйте факты и карты из эталона. Напишите ответ только для текущего вопроса.
Любое новое психологическое объяснение, которого нет в проверенном плане, запрещено.
Верните только JSON.
""".strip()


def normalize_json_transport_v6(raw: str) -> str:
    text = raw.lstrip("\ufeff").replace("\u00a0", " ").strip()
    opening = re.match(r"^\u0060\u0060\u0060(?:json)?\s*", text, re.IGNORECASE)
    if opening:
        text = text[opening.end():]
        text = re.sub(r"\s*\u0060\u0060\u0060\s*$", "", text)
    return text.strip()


def looks_truncated_json_v6(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    if stripped.endswith((",", ":", "{", "[")):
        return True
    in_string = False
    escaped = False
    braces = brackets = 0
    for char in stripped:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            braces += 1
        elif char == "}":
            braces -= 1
        elif char == "[":
            brackets += 1
        elif char == "]":
            brackets -= 1
    return in_string or braces > 0 or brackets > 0


def parse_json_v6(raw: str | None) -> tuple[dict[str, Any] | None, list[str]]:
    if not raw:
        return None, ["empty_answer"]
    normalized = normalize_json_transport_v6(raw)
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        return None, [
            "truncated_json" if looks_truncated_json_v6(normalized) else "invalid_json"
        ]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    return payload, []


def unpack_reply_v6(reply: Any) -> tuple[str | None, dict[str, Any]]:
    if isinstance(reply, str) or reply is None:
        return reply, {"finish_reason": None, "usage": None}
    if isinstance(reply, dict):
        text = reply.get("text")
        return (
            text if isinstance(text, str) else None,
            {
                "finish_reason": reply.get("finish_reason"),
                "usage": reply.get("usage"),
            },
        )
    return None, {"finish_reason": None, "usage": None}


def word_form_pattern_v6(word: str) -> str:
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


def card_pattern_v6(name: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", name)
    return rf"(?<!\w){r'[\s–—-]+'.join(word_form_pattern_v6(word) for word in words)}(?!\w)"


def normalize_card_search_v6(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", normalized)
    return normalized.translate(LATIN_TO_CYRILLIC_LOOKALIKES_V6)


def missing_cards_v6(text: str, cards: list[dict[str, Any]]) -> list[str]:
    normalized_text = normalize_card_search_v6(text)
    return [
        card["name"]
        for card in cards
        if not re.search(card_pattern_v6(card["name"]), text, re.IGNORECASE)
        and not re.search(
            card_pattern_v6(normalize_card_search_v6(card["name"])),
            normalized_text,
            re.IGNORECASE,
        )
    ]


def validate_analysis_v6(
    payload: dict[str, Any],
    *,
    question: str,
    cards: list[dict[str, Any]],
    route: str,
    topic: str = "general",
) -> list[str]:
    issues: list[str] = []
    topic_profile = route_topic_profile_v6(route, topic)
    string_fields = (
        "question_route",
        "interaction_code",
        "focus_code",
        "tendency_code",
        "criterion_code",
    )
    for field in string_fields:
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            issues.append(f"missing:{field}")

    expected_fields = set(ANALYSIS_SCHEMA_V6["required"])
    unexpected_fields = set(payload) - expected_fields
    if unexpected_fields:
        issues.append("unexpected_analysis_fields:" + "|".join(sorted(unexpected_fields)))
    if payload.get("question_route") != route:
        issues.append("route_mismatch")
    if payload.get("interaction_code") not in INTERACTION_CODES_V6:
        issues.append("invalid_interaction_code")
    if payload.get("tendency_code") not in ROUTE_CONFIG_V6[route]["tendencies"]:
        issues.append("invalid_tendency")
    if payload.get("focus_code") not in topic_profile["focus_codes"]:
        issues.append("invalid_focus_code")
    if payload.get("criterion_code") not in topic_profile["criterion_codes"]:
        issues.append("invalid_criterion_code")

    quotes = payload.get("question_quotes")
    normalized_question = normalize_text_v6(question)
    if not isinstance(quotes, list) or not 1 <= len(quotes) <= 3:
        issues.append("invalid:question_quotes")
    else:
        if any(
            not isinstance(quote, str)
            or not quote.strip()
            or normalize_text_v6(quote) not in normalized_question
            for quote in quotes
        ):
            issues.append("unsupported_question_quote")
    return list(dict.fromkeys(issues))


def count_words_v6(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-–][A-Za-zА-Яа-яЁё0-9]+)?", text))


def split_paragraphs_v6(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    return [
        part.strip()
        for part in re.split(r"\n[ \t]*\n+", normalized)
        if part.strip()
    ]


def normalize_final_layout_v6(text: str) -> str:
    normalized = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    normalized = re.sub(r"\r\n?", "\n", normalized).strip()
    paragraphs = split_paragraphs_v6(normalized)
    if len(paragraphs) == 3:
        return "\n\n".join(paragraphs)

    nonempty_lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if len(nonempty_lines) == 3:
        return "\n\n".join(nonempty_lines)
    return normalized


def criterion_statement_v6(paragraph: str) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip())
        if sentence.strip()
    ]
    if len(sentences) > 1 and sentences[-1].endswith("?"):
        return " ".join(sentences[:-1])
    return paragraph.strip()


def validate_final_v6(
    payload: dict[str, Any],
    *,
    question: str,
    cards: list[dict[str, Any]],
    route: str | None = None,
    topic: str = "general",
) -> list[str]:
    text = payload.get("final_text")
    if not isinstance(text, str) or not text.strip():
        return ["missing:final_text"]
    text = normalize_final_layout_v6(text)
    route = route or infer_question_route_v6(question)
    issues: list[str] = []
    paragraphs = split_paragraphs_v6(text)
    if len(paragraphs) != 3:
        issues.append("paragraph_count")
    words = count_words_v6(text)
    if words < 100 or words > 170:
        issues.append(f"word_count:{words}")
    if not text.rstrip().endswith("?"):
        issues.append("missing_final_question")
    missing = missing_cards_v6(text, cards)
    if missing:
        issues.append("final_missing_cards:" + "|".join(missing))
    if not re.search(
        r"\b(?:символик\w*|расклад скорее|сочетание скорее)\b",
        paragraphs[0] if paragraphs else text,
        re.IGNORECASE,
    ):
        issues.append("missing_symbolic_frame")
    if has_high_risk_claim_v6(text):
        issues.append("high_risk_claim")
    if any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in PSEUDO_PSYCHOLOGY_PATTERNS_V6
    ):
        issues.append("pseudo_psychology")
    if any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in ADAPTATION_AND_BLAME_PATTERNS_V6
    ):
        issues.append("adaptation_or_user_blame")
    unsupported_markers = unsupported_inference_markers_v6(
        text,
        question=question,
        cards=cards,
    )
    if unsupported_markers:
        issues.append("unsupported_inference:" + "|".join(unsupported_markers))
    normalized_question = normalize_text_v6(question)
    is_love_topic = normalize_topic_v6(topic) == "love" or any(
        marker in normalized_question for marker in RELATIONSHIP_QUESTION_MARKERS_V6
    )
    if is_love_topic and any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in LOVE_DOMAIN_LEAK_PATTERNS_V6
    ):
        issues.append("domain_style_leak:career_to_love")
    if (
        route == "personal_choice"
        and any(marker in normalized_question for marker in RELATIONSHIP_QUESTION_MARKERS_V6)
        and paragraphs
    ):
        criterion_paragraph = normalize_text_v6(
            criterion_statement_v6(paragraphs[-1])
        )
        if not any(
            marker in criterion_paragraph
            for marker in RELATIONSHIP_CRITERION_MARKERS_V6
        ):
            issues.append("missing_relationship_reality_criterion")
    if route == "initiative" and paragraphs:
        criterion_paragraph = normalize_text_v6(
            criterion_statement_v6(paragraphs[-1])
        )
        if not any(
            marker in criterion_paragraph
            for marker in INITIATIVE_CRITERION_MARKERS_V6
        ):
            issues.append("missing_initiative_reality_criterion")
    for pattern in UNSUPPORTED_STORY_PATTERNS_V6:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and normalize_text_v6(match.group(0)) not in normalized_question:
            issues.append("unsupported_story")
            break
    if re.match(r"\s*(?:привет|здравствуйте|приветствую)\b", text, re.IGNORECASE):
        issues.append("greeting")
    return list(dict.fromkeys(issues))


def clean_stars_v6(text: str) -> str:
    cleaned = re.sub(r"\*\*(?=\S)([^*\n]*?\S)\*\*", r"\1", text)
    return re.sub(r"(?<!\*)\*(?=\S)([^*\n]*?\S)\*(?!\*)", r"\1", cleaned).strip()


def fallback_v6(question: str, cards: list[dict[str, Any]], route: str) -> str:
    names = [card["name"] for card in cards]
    if route == "initiative" and len(names) >= 3:
        return (
            "По символике сочетания нет достаточной опоры рассчитывать на самостоятельный "
            "первый шаг: возможность контакта остаётся открытой, но не складывается в "
            "уверенное указание. Здесь важно различать надежду на проявление и то, что "
            "действительно можно считать инициативой.\n\n"
            f"{names[0]} поддерживает тему движения и инициативы, однако {names[1]} вносит "
            f"сильное противоречие и мешает читать импульс как устойчивый. {names[2]} "
            "сохраняет надежду и перспективу, но не превращает их в совершённое действие. "
            "Вместе карты показывают разницу между возможностью контакта и реальным шагом.\n\n"
            "Проверяемым подтверждением будет содержательное сообщение или самостоятельное "
            "продолжение разговора без вашего предварительного действия. Какое проявление "
            "вы сочтёте настоящей инициативой и где для вас проходит граница между открытой "
            "возможностью и ожиданием, которое занимает слишком много внимания?"
        )
    if route == "personal_choice" and len(names) >= 3:
        normalized_question = normalize_text_v6(question)
        if any(
            marker in normalized_question
            for marker in RELATIONSHIP_QUESTION_MARKERS_V6
        ):
            return (
                "По символике расклада решение зависит от того, соответствует ли такой "
                "контакт вашим ожиданиям от близости и устойчивости. Тёплые эпизоды "
                "могут быть значимы, но сами по себе ещё не отвечают на вопрос о ценности "
                "продолжения этой связи.\n\n"
                f"{names[0]} показывает привлекательную сторону общения, {names[1]} "
                f"подчёркивает цену дистанции, а {names[2]} связывает их через подходящую "
                "вам меру участия. Карты не предлагают приспособиться к неудобному ритму: "
                "они помогают сопоставить приятные моменты с тем, чего вам не хватает "
                "между ними.\n\n"
                "Проверяемым ориентиром станет взаимность инициативы после пауз и то, "
                "поддерживается ли контакт усилиями обеих сторон. Какой ритм общения и "
                "уровень взаимности необходимы вам, чтобы продолжение имело ценность?"
            )
        return (
            "По символике расклада решение зависит от того, насколько рассматриваемый "
            "вариант соответствует вашим собственным условиям, а не только от его "
            "привлекательной стороны.\n\n"
            f"{names[0]} показывает ценность варианта, {names[1]} добавляет его главное "
            f"противоречие, а {names[2]} возвращает выбор к критерию, который можно "
            "проверить в реальности. Карты не выбирают вместо вас, но делают цену решения "
            "более заметной.\n\n"
            "Ориентиром станет то, выполняется ли важное для вас условие выбора. Какое "
            "условие должно быть соблюдено, чтобы этот вариант действительно вам подходил?"
        )
    return (
        "По символике расклада вопрос остаётся открытым. Карты показывают несколько "
        "ракурсов, но не дают основания выдавать один из них за установленный факт.\n\n"
        "Общий рисунок стоит сопоставить с тем, что уже известно из реальной ситуации.\n\n"
        "Какой проверяемой информации сейчас не хватает для более ясного решения?"
    )


def decorate_transport_issues_v6(
    issues: list[str],
    diagnostics: dict[str, Any],
) -> list[str]:
    reason = str(diagnostics.get("finish_reason") or "").upper()
    return [
        "truncated_json:max_tokens"
        if issue == "truncated_json" and "MAX_TOKENS" in reason
        else issue
        for issue in issues
    ]


def generate_reading_v6(
    *,
    question: str,
    cards: list[dict[str, Any]],
    analysis_call: Callable[[str], Any],
    editor_call: Callable[[str], Any],
    topic: str = "general",
) -> dict[str, Any]:
    route = infer_question_route_v6(question)
    if route not in ROUTE_CONFIG_V6:
        return {
            "text": fallback_v6(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "routing",
            "issues": ["unsupported_route"],
            "ai_requests": 0,
            "analysis_diagnostics": None,
            "editor_diagnostics": None,
        }

    analysis_reply = analysis_call(build_analysis_prompt_v6(question, cards, route, topic))
    analysis_raw, analysis_diagnostics = unpack_reply_v6(analysis_reply)
    analysis, issues = parse_json_v6(analysis_raw)
    issues = decorate_transport_issues_v6(issues, analysis_diagnostics)
    if analysis is not None:
        issues.extend(
            validate_analysis_v6(
                analysis,
                question=question,
                cards=cards,
                route=route,
                topic=topic,
            )
        )
    if analysis is None or issues:
        return {
            "text": fallback_v6(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "analysis",
            "issues": list(dict.fromkeys(issues)),
            "ai_requests": 1,
            "analysis_diagnostics": analysis_diagnostics,
            "editor_diagnostics": None,
            "rejected_analysis": analysis,
        }

    editor_reply = editor_call(
        build_editor_prompt_v6(question, cards, route, analysis, topic)
    )
    editor_raw, editor_diagnostics = unpack_reply_v6(editor_reply)
    final_payload, final_issues = parse_json_v6(editor_raw)
    final_issues = decorate_transport_issues_v6(final_issues, editor_diagnostics)
    rejected_text = None
    if final_payload is not None:
        if isinstance(final_payload.get("final_text"), str):
            normalized_final = normalize_final_layout_v6(final_payload["final_text"])
            final_payload = {**final_payload, "final_text": normalized_final}
            rejected_text = clean_stars_v6(normalized_final)
        final_issues.extend(
            validate_final_v6(
                final_payload,
                question=question,
                cards=cards,
                route=route,
                topic=topic,
            )
        )
    if final_payload is None or final_issues:
        return {
            "text": fallback_v6(question, cards, route),
            "route": route,
            "used_fallback": True,
            "stage": "editor",
            "issues": list(dict.fromkeys(final_issues)),
            "ai_requests": 2,
            "analysis_diagnostics": analysis_diagnostics,
            "editor_diagnostics": editor_diagnostics,
            "rejected_text": rejected_text,
            "analysis": analysis,
        }

    return {
        "text": clean_stars_v6(final_payload["final_text"]),
        "route": route,
        "used_fallback": False,
        "stage": "complete",
        "issues": [],
        "ai_requests": 2,
        "analysis": analysis,
        "analysis_diagnostics": analysis_diagnostics,
        "editor_diagnostics": editor_diagnostics,
        "rejected_text": None,
    }
