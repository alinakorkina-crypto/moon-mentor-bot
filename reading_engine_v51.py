"""Reading Engine v5.1: robust JSON transport and finish diagnostics."""

import json
import re
from typing import Any, Callable

from reading_engine_v5 import (
    ANALYSIS_SCHEMA_V5,
    ANALYSIS_SYSTEM_V5,
    EDITOR_SCHEMA_V5,
    EDITOR_SYSTEM_V5,
    build_analysis_prompt_v5,
    build_editor_prompt_v5,
    build_local_fallback_v5,
    clean_markdown_stars_v5,
    validate_analysis_v5,
    validate_final_text_v5,
)


ANALYSIS_SCHEMA_V51 = ANALYSIS_SCHEMA_V5
EDITOR_SCHEMA_V51 = EDITOR_SCHEMA_V5
ANALYSIS_SYSTEM_V51 = ANALYSIS_SYSTEM_V5
EDITOR_SYSTEM_V51 = EDITOR_SYSTEM_V5


def unpack_model_reply_v51(reply: Any) -> tuple[str | None, dict[str, Any]]:
    """Accept plain text in tests or a diagnostic reply from ai_reader_v51."""
    if isinstance(reply, str) or reply is None:
        return reply, {"finish_reason": None}
    if isinstance(reply, dict):
        text = reply.get("text")
        diagnostics = {
            "finish_reason": reply.get("finish_reason"),
            "usage": reply.get("usage"),
        }
        return text if isinstance(text, str) else None, diagnostics
    return None, {"finish_reason": None, "reply_type": type(reply).__name__}


def normalize_json_transport_v51(raw: str) -> str:
    """Normalize transport-only characters without changing JSON content."""
    text = raw.lstrip("\ufeff").replace("\u00a0", " ").strip()
    opening = re.match(r"^\u0060\u0060\u0060(?:json)?\s*", text, re.IGNORECASE)
    if opening:
        text = text[opening.end():]
        text = re.sub(r"\s*\u0060\u0060\u0060\s*$", "", text)
    return text.strip()


def _looks_truncated_json_v51(text: str) -> bool:
    """Conservatively identify an unfinished object or array."""
    stripped = text.rstrip()
    if not stripped:
        return False
    if stripped.endswith((",", ":", "{", "[")):
        return True

    in_string = False
    escaped = False
    braces = 0
    brackets = 0
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


def parse_json_object_v51(raw: str | None) -> tuple[dict[str, Any] | None, list[str]]:
    if not raw:
        return None, ["empty_answer"]
    normalized = normalize_json_transport_v51(raw)
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        issue = "truncated_json" if _looks_truncated_json_v51(normalized) else "invalid_json"
        return None, [issue]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    return payload, []


def _decorate_transport_issues(
    issues: list[str],
    diagnostics: dict[str, Any],
) -> list[str]:
    finish_reason = str(diagnostics.get("finish_reason") or "").upper()
    decorated = list(issues)
    if "truncated_json" in decorated and "MAX_TOKENS" in finish_reason:
        decorated = [
            "truncated_json:max_tokens" if issue == "truncated_json" else issue
            for issue in decorated
        ]
    return list(dict.fromkeys(decorated))


def generate_personal_reading_v51(
    *,
    user_question: str,
    cards: list[dict[str, Any]],
    analysis_call: Callable[[str], Any],
    editor_call: Callable[[str], Any],
    topic: str = "general",
) -> dict[str, Any]:
    analysis_reply = analysis_call(build_analysis_prompt_v5(user_question, cards, topic))
    analysis_raw, analysis_diagnostics = unpack_model_reply_v51(analysis_reply)
    analysis, issues = parse_json_object_v51(analysis_raw)
    issues = _decorate_transport_issues(issues, analysis_diagnostics)
    if analysis is not None:
        issues.extend(
            validate_analysis_v5(
                analysis,
                user_question=user_question,
                cards=cards,
            )
        )
    if analysis is None or issues:
        return {
            "text": build_local_fallback_v5(user_question, cards),
            "used_fallback": True,
            "stage": "analysis",
            "issues": list(dict.fromkeys(issues)),
            "ai_requests": 1,
            "analysis_diagnostics": analysis_diagnostics,
            "editor_diagnostics": None,
        }

    editor_reply = editor_call(build_editor_prompt_v5(user_question, cards, analysis))
    editor_raw, editor_diagnostics = unpack_model_reply_v51(editor_reply)
    final_payload, editor_issues = parse_json_object_v51(editor_raw)
    editor_issues = _decorate_transport_issues(editor_issues, editor_diagnostics)
    if final_payload is not None:
        editor_issues.extend(validate_final_text_v5(final_payload, cards=cards))
    if final_payload is None or editor_issues:
        return {
            "text": build_local_fallback_v5(user_question, cards),
            "used_fallback": True,
            "stage": "editor",
            "issues": list(dict.fromkeys(editor_issues)),
            "ai_requests": 2,
            "analysis_diagnostics": analysis_diagnostics,
            "editor_diagnostics": editor_diagnostics,
        }

    return {
        "text": clean_markdown_stars_v5(final_payload["final_text"]),
        "used_fallback": False,
        "stage": "complete",
        "issues": [],
        "ai_requests": 2,
        "analysis": analysis,
        "analysis_diagnostics": analysis_diagnostics,
        "editor_diagnostics": editor_diagnostics,
    }
