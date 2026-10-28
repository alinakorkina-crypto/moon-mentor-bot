"""Real SDK and HTTPX routing with in-memory transports; artificial data only."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

import httpx

from ai_reader_openai_v8 import ask_openai_v8, _safe_error_message
from reading_engine_v8 import generate_reading_v8, unpack_reply_v8
from test_reading_engine_v8 import (
    INITIATIVE_CARDS, INITIATIVE_QUESTION, VALID_INITIATIVE_TEXT,
)


class OpenAITransportTests(unittest.TestCase):
    def test_exception_diagnostics_are_redacted_and_reach_engine(self):
        message = (
            'Failed: sk-proj-artificial-key; Bearer artificial-token '
            '__SECRET_TEST_VALUE__ https://user:password@proxy.invalid:8080/path'
        )
        with patch('ai_reader_openai_v8.httpx.Client',
                   side_effect=RuntimeError(message)):
            reply = ask_openai_v8('offline diagnostic test')
        self.assertEqual(reply['error_type'], 'RuntimeError')
        self.assertEqual(reply['error_message'],
            'Failed: [REDACTED]; Bearer [REDACTED] '
            '[REDACTED] https://[REDACTED]@proxy.invalid:8080/path')
        _, info, _ = unpack_reply_v8(reply)
        self.assertEqual(info['error_type'], 'RuntimeError')
        self.assertEqual(info['error_message'], reply['error_message'])
        output = repr(info)
        for secret in ('sk-proj-artificial-key', 'artificial-token',
                       '__SECRET_TEST_VALUE__', 'user:password'):
            self.assertNotIn(secret, output)

    def test_redacts_multiple_credentials_and_preserves_useful_details(self):
        message = ('bEaReR token-one, Bearer token-two\n'
                   'sk-test-one sk-test-two __SECRET_ONE__ __SECRET_TWO__ '
                   'http://alice:p%40ss@host.invalid/path '
                   'socks5://bob:pass@other.invalid:1080; timeout')
        safe = _safe_error_message(message)
        for secret in ('token-one', 'token-two', 'sk-test-one', 'sk-test-two',
                       '__SECRET_ONE__', '__SECRET_TWO__', 'alice', 'p%40ss',
                       'bob', ':pass@'):
            self.assertNotIn(secret, safe)
        self.assertIn('host.invalid/path', safe)
        self.assertIn('other.invalid:1080; timeout', safe)
        self.assertEqual(_safe_error_message('Connection timed out'),
                         'Connection timed out')

    def run_http_case(self, outcome=200, *, proxy=False, no_proxy=False,
                      body=None, status='completed', raw_text=None):
        calls = {'direct': [], 'proxy': []}
        raw = json.dumps(body if body is not None else
                         {'final_text': VALID_INITIATIVE_TEXT}, ensure_ascii=False)
        if raw_text is not None:
            raw = raw_text
        usage = {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150}

        def transport(route):
            def handle(request):
                calls[route].append(request)
                if isinstance(outcome, type) and issubclass(outcome, Exception):
                    raise outcome('synthetic-sensitive-message', request=request)
                if outcome == 200:
                    return httpx.Response(200, json={
                        'id': 'resp_offline', 'object': 'response', 'created_at': 0,
                        'model': 'offline-model', 'status': status, 'usage': usage,
                        'output': [{'id': 'msg_offline', 'type': 'message',
                                    'role': 'assistant', 'status': 'completed',
                                    'content': [{'type': 'output_text', 'annotations': [],
                                                 'text': raw}]}],
                    })
                return httpx.Response(outcome,
                    headers={'Location': 'https://example.invalid/redirect'},
                    json={'error': {'message': 'synthetic-sensitive-message'}})
            return httpx.MockTransport(handle)

        direct, proxied = transport('direct'), transport('proxy')
        environment = {'OPENAI_API_KEY': 'offline-test-only',
                       'OPENAI_BASE_URL': 'https://api.openai.com/v1'}
        if proxy:
            environment['HTTPS_PROXY'] = 'http://fake-user:fake-password@proxy.invalid:8080'
        if no_proxy:
            environment['NO_PROXY'] = 'api.openai.com'
        output = io.StringIO()
        # Preserve real Client routing: replace only the transports it constructs.
        with patch.dict('os.environ', environment, clear=True), \
             patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(httpx.Client, '_init_transport', return_value=direct), \
             patch.object(httpx.Client, '_init_proxy_transport', return_value=proxied), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = generate_reading_v8(
                question=INITIATIVE_QUESTION, cards=INITIATIVE_CARDS,
                model_call=ask_openai_v8,
            )
        selected = 'proxy' if proxy and not no_proxy else 'direct'
        self.assertEqual(len(calls[selected]), 1)
        self.assertEqual(len(calls['direct' if selected == 'proxy' else 'proxy']), 0)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('fake-password', repr(result))
        return result, raw

    def test_success_direct_and_https_proxy(self):
        for proxy in (False, True):
            with self.subTest(proxy=proxy):
                result, _ = self.run_http_case(proxy=proxy)
                self.assertEqual(result['status'], 'success')

    def test_no_proxy_selects_direct_transport(self):
        result, _ = self.run_http_case(proxy=True, no_proxy=True)
        self.assertEqual(result['status'], 'success')

    def test_errors_and_redirect_never_retry_on_either_transport(self):
        for proxy in (False, True):
            for outcome in (429, 500, 307, httpx.ReadTimeout, httpx.ConnectError):
                with self.subTest(proxy=proxy, outcome=outcome):
                    result, _ = self.run_http_case(outcome, proxy=proxy)
                    self.assertEqual(result['status'], 'error')
                    self.assertIsNone(result['text'])

    def test_schema_error_preserves_text_status_usage(self):
        text = '  **Он\u00a0хочет написать первым.**\r\n  '
        result, raw = self.run_http_case(body={'final_text': text, 'extra': 'artificial'})
        self.assertEqual(result['status'], 'error')
        self.assertIn('schema_validation_error', result['issues'])
        self.assertEqual(result['rejected_text'], text)
        self.assertEqual(result['raw_response_text'], raw)
        self.assertEqual(result['diagnostics']['status'], 'completed')
        self.assertEqual(result['diagnostics']['usage']['total_tokens'], 150)

    def test_invalid_json_preserves_response_status_and_usage(self):
        raw = '  {"final_text": "**искусственный\u00a0ответ**'
        result, _ = self.run_http_case(raw_text=raw)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['raw_response_text'], raw)
        self.assertEqual(result['diagnostics']['status'], 'completed')
        self.assertEqual(result['diagnostics']['usage']['total_tokens'], 150)
        self.assertIsNone(result['rejected_text'])

    def test_wrong_field_type_preserves_raw_response_and_usage(self):
        result, raw = self.run_http_case(body={'final_text': 123})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['raw_response_text'], raw)
        self.assertIsNone(result['rejected_text'])
        self.assertEqual(result['diagnostics']['usage']['input_tokens'], 100)

    def test_incomplete_response_preserves_available_text(self):
        result, raw = self.run_http_case(status='incomplete')
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['raw_response_text'], raw)
        self.assertEqual(result['rejected_text'], VALID_INITIATIVE_TEXT)


if __name__ == '__main__':
    unittest.main()
