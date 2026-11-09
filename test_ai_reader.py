"""Offline tests for the plain-text OpenAI transport."""

import json
import types
import unittest
from unittest.mock import Mock, patch

import ai_reader


class PlainOpenAITransportTests(unittest.TestCase):
    def test_sdk_makes_one_call_without_retries(self):
        response = types.SimpleNamespace(output_text="  Готовый ответ.  ")
        client = Mock()
        client.responses.create.return_value = response
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=False)
        http_context = Mock()
        http_context.__enter__ = Mock(return_value=Mock())
        http_context.__exit__ = Mock(return_value=False)
        with patch.object(ai_reader.httpx, "Client", return_value=http_context), \
             patch.object(ai_reader, "OpenAI", return_value=context) as constructor:
            result = ai_reader.ask_openai("Тестовый запрос")
        self.assertEqual(result, "Готовый ответ.")
        constructor.assert_called_once()
        self.assertEqual(constructor.call_args.kwargs["max_retries"], 0)
        client.responses.create.assert_called_once()

    def test_sdk_error_returns_none_without_secret_details(self):
        with patch.object(ai_reader.httpx, "Client",
                          side_effect=RuntimeError("sk-artificial-secret")):
            result = ai_reader.ask_openai("Тест")
        self.assertIsNone(result)

    def test_curl_sends_one_request_and_reads_text(self):
        body = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": "Ответ curl"}
        ]}]}
        completed = types.SimpleNamespace(
            returncode=0, stdout=json.dumps(body) + "\n200", stderr="")
        with patch.dict(ai_reader.os.environ, {
                "OPENAI_API_KEY": "offline-test-only", "OPENAI_TRANSPORT": "curl"
             }, clear=True), \
             patch.object(ai_reader.subprocess, "run", return_value=completed) as run:
            result = ai_reader.ask_openai("Тест curl")
        self.assertEqual(result, "Ответ curl")
        run.assert_called_once()
        self.assertNotIn("offline-test-only", repr(run.call_args))

    def test_curl_rejects_missing_key_before_subprocess(self):
        with patch.dict(ai_reader.os.environ, {"OPENAI_TRANSPORT": "curl"}, clear=True), \
             patch.object(ai_reader.subprocess, "run") as run:
            self.assertIsNone(ai_reader.ask_openai("Тест"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
