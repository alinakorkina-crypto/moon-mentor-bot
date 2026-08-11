"""Diagnostic control preview for Reading Engine v5.1."""

from ai_reader_v51 import ask_gemini_analysis_v51, ask_gemini_editor_v51
from preview_reading_v5 import CARDS, QUESTION
from reading_engine_v5 import count_words_v5
from reading_engine_v51 import generate_personal_reading_v51


def _diagnostic_line(label: str, diagnostics) -> str:
    if not diagnostics:
        return f"{label}: —"
    finish = diagnostics.get("finish_reason") or "не указан"
    usage = diagnostics.get("usage") or {}
    total = usage.get("total_token_count", "—")
    thoughts = usage.get("thoughts_token_count", "—")
    output = usage.get("candidates_token_count", "—")
    return (
        f"{label}: finish_reason={finish}, "
        f"total_tokens={total}, thoughts={thoughts}, output={output}"
    )


def main() -> None:
    calls = {"analysis": 0, "editor": 0}

    def analysis_call(prompt: str):
        calls["analysis"] += 1
        return ask_gemini_analysis_v51(prompt)

    def editor_call(prompt: str):
        calls["editor"] += 1
        return ask_gemini_editor_v51(prompt)

    result = generate_personal_reading_v51(
        user_question=QUESTION,
        cards=CARDS,
        analysis_call=analysis_call,
        editor_call=editor_call,
    )

    print("\n===== READING ENGINE V5.1: TRANSPORT-DIAGNOSTIC PREVIEW =====\n")
    print(f"Вопрос: {QUESTION}")
    print("Карты: " + " — ".join(card["name"] for card in CARDS) + "\n")
    print(result["text"])
    print(f"\nСлов: {count_words_v5(result['text'])}")
    print(f"Абзацев: {len(result['text'].split(chr(10) + chr(10)))}")
    print("Источник: " + ("локальный fallback" if result["used_fallback"] else "AI-анализ + AI-редактор"))
    print(f"Этап: {result['stage']}")
    print("Валидация: " + (", ".join(result["issues"]) if result["issues"] else "OK"))
    print(_diagnostic_line("Аналитик", result.get("analysis_diagnostics")))
    print(_diagnostic_line("Редактор", result.get("editor_diagnostics")))
    print(f"AI-запросов: {calls['analysis'] + calls['editor']}")


if __name__ == "__main__":
    main()
