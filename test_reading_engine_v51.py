import json
import unittest

from reading_engine_v51 import (
    generate_personal_reading_v51,
    normalize_json_transport_v51,
    parse_json_object_v51,
    unpack_model_reply_v51,
)
from test_reading_engine_v5 import CARDS, QUESTION, valid_analysis, valid_final


class ReadingEngineV51Tests(unittest.TestCase):
    def test_non_breaking_spaces_are_normalized(self):
        raw = '{\n\u00a0 "question_mode": "initiative"\n}'
        payload, issues = parse_json_object_v51(raw)
        self.assertEqual(payload, {"question_mode": "initiative"})
        self.assertEqual(issues, [])

    def test_markdown_json_fence_is_removed(self):
        raw = '~~~placeholder~~~'
        raw = raw.replace("~~~placeholder~~~", "```json\n{\"ok\": true}\n```")
        payload, issues = parse_json_object_v51(raw)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(issues, [])

    def test_bom_is_removed(self):
        payload, issues = parse_json_object_v51('\ufeff{"ok": true}')
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(issues, [])

    def test_unfinished_object_is_reported_as_truncated(self):
        payload, issues = parse_json_object_v51('{"facts_used": ["текст"],')
        self.assertIsNone(payload)
        self.assertEqual(issues, ["truncated_json"])

    def test_balanced_but_invalid_object_stays_invalid(self):
        payload, issues = parse_json_object_v51("{'ok': true}")
        self.assertIsNone(payload)
        self.assertEqual(issues, ["invalid_json"])

    def test_normalizer_does_not_extract_arbitrary_surrounding_prose(self):
        normalized = normalize_json_transport_v51('Ответ: {"ok": true}')
        self.assertEqual(normalized, 'Ответ: {"ok": true}')

    def test_diagnostic_reply_is_unpacked(self):
        text, diagnostics = unpack_model_reply_v51(
            {
                "text": '{"ok": true}',
                "finish_reason": "STOP",
                "usage": {"total_token_count": 10},
            }
        )
        self.assertEqual(text, '{"ok": true}')
        self.assertEqual(diagnostics["finish_reason"], "STOP")

    def test_max_tokens_is_attached_to_truncation_issue(self):
        result = generate_personal_reading_v51(
            user_question=QUESTION,
            cards=CARDS,
            analysis_call=lambda prompt: {
                "text": '{"facts_used": [',
                "finish_reason": "MAX_TOKENS",
                "usage": {"total_token_count": 4096},
            },
            editor_call=lambda prompt: None,
        )
        self.assertEqual(result["issues"], ["truncated_json:max_tokens"])
        self.assertEqual(result["stage"], "analysis")
        self.assertEqual(result["ai_requests"], 1)

    def test_nbsp_analysis_can_reach_editor(self):
        analysis_raw = json.dumps(valid_analysis(), ensure_ascii=False).replace(" ", "\u00a0")
        result = generate_personal_reading_v51(
            user_question=QUESTION,
            cards=CARDS,
            analysis_call=lambda prompt: {
                "text": analysis_raw,
                "finish_reason": "STOP",
            },
            editor_call=lambda prompt: {
                "text": json.dumps(valid_final(), ensure_ascii=False),
                "finish_reason": "STOP",
            },
        )
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["ai_requests"], 2)

    def test_invalid_editor_reports_editor_diagnostics(self):
        result = generate_personal_reading_v51(
            user_question=QUESTION,
            cards=CARDS,
            analysis_call=lambda prompt: {
                "text": json.dumps(valid_analysis(), ensure_ascii=False),
                "finish_reason": "STOP",
            },
            editor_call=lambda prompt: {
                "text": '{"final_text":',
                "finish_reason": "MAX_TOKENS",
            },
        )
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["stage"], "editor")
        self.assertEqual(result["issues"], ["truncated_json:max_tokens"])
        self.assertEqual(result["editor_diagnostics"]["finish_reason"], "MAX_TOKENS")


if __name__ == "__main__":
    unittest.main()
