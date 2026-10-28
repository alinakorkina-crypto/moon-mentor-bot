"""Offline curl transport checks; no subprocess or network is executed."""
import json
import contextlib
import io
import os
import socket
import subprocess
import unittest
from unittest.mock import patch

import ai_reader_openai_v8 as reader


class CurlTransportTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            'OPENAI_TRANSPORT': 'curl', 'OPENAI_API_KEY': 'offline-key-only',
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for target in ('socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Network forbidden'))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(reader, 'OpenAI',
                             side_effect=AssertionError('SDK forbidden in curl mode'))
        guard.start()
        self.addCleanup(guard.stop)

    def response(self, **overrides):
        data = {
            'status': 'completed', 'model': 'offline-model',
            'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': '{"final_text":"offline text"}'},
            ]}],
            'usage': {'input_tokens': 10, 'output_tokens': 8, 'total_tokens': 18,
                      'input_tokens_details': {'cached_tokens': 2},
                      'output_tokens_details': {'reasoning_tokens': 3}},
        }
        data.update(overrides)
        return data

    def call(self, data=None, status=200, *, returncode=0, raw=None, exception=None):
        def run(argv, **kwargs):
            self.argv = argv
            self.request = json.loads(kwargs['input'])
            self.assertEqual(argv.count('https://api.openai.com/v1/responses'), 1)
            self.assertEqual(argv[0:2], ['curl', '--disable'])
            self.assertEqual(argv[argv.index('--retry') + 1], '0')
            self.assertIn('--no-location', argv)
            self.assertEqual(argv[argv.index('--max-redirs') + 1], '0')
            self.assertEqual(argv[argv.index('--data-binary') + 1], '@-')
            self.assertNotIn('offline-key-only', repr(argv))
            self.assertNotIn('offline-key-only', kwargs['input'])
            self.assertEqual(os.read(kwargs['pass_fds'][0], 4096),
                             b'Authorization: Bearer offline-key-only\n')
            if exception:
                raise exception
            body = raw if raw is not None else json.dumps(data or self.response())
            return subprocess.CompletedProcess(argv, returncode,
                stdout=f'{body}\n{status}', stderr='secret stderr must never be returned')
        with patch.object(reader.subprocess, 'run', side_effect=run) as mocked:
            result = reader.ask_openai_v8('offline prompt')
        mocked.assert_called_once()
        return result

    def test_request_matches_sdk_parameters_and_parses_usage(self):
        result = self.call()
        self.assertEqual(self.request, {
            'model': reader.MODEL_NAME, 'reasoning': {'effort': 'low'},
            'max_output_tokens': 900,
            'input': [{'role': 'system', 'content': reader.SYSTEM_PROMPT_V8},
                      {'role': 'user', 'content': 'offline prompt'}],
            'text': {'format': {'type': 'json_schema', 'name': 'reading_v8',
                               'strict': True, 'schema': reader.FINAL_SCHEMA_V8}},
        })
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['model'], 'offline-model')
        self.assertEqual(result['payload'], {'final_text': 'offline text'})
        self.assertEqual(result['usage'], {
            'input_tokens': 10, 'cached_input_tokens': 2, 'output_tokens': 8,
            'reasoning_tokens': 3, 'total_tokens': 18,
        })

    def test_invalid_keys_are_rejected_before_subprocess(self):
        for key in (None, '', ' \t\r\n', '__SECRET__',
                    '  __SECRET_TEST_VALUE__\n', '__SECRET value__'):
            with self.subTest(key=key):
                if key is None:
                    os.environ.pop('OPENAI_API_KEY', None)
                else:
                    os.environ['OPENAI_API_KEY'] = key
                with patch.object(reader.subprocess, 'run') as mocked:
                    result = reader.ask_openai_v8('offline prompt')
                mocked.assert_not_called()
                self.assertEqual(result['error_type'], 'ValueError')
                self.assertEqual(result['error_message'], 'Invalid OPENAI_API_KEY')

    def test_keys_are_stripped_without_prefix_length_or_format_checks(self):
        for key in ('x', 'arbitrary-key', '  arbitrary-key\r\n',
                    '__SECRET_not_a_placeholder', 'punctuation!@#', 'inside\nnewline'):
            with self.subTest(key=key):
                os.environ['OPENAI_API_KEY'] = key

                def run(argv, **kwargs):
                    self.assertEqual(os.read(kwargs['pass_fds'][0], 4096),
                        ('Authorization: Bearer ' + key.strip() + '\n').encode())
                    return subprocess.CompletedProcess(argv, 0,
                        stdout=json.dumps(self.response()) + '\n200', stderr='')

                with patch.object(reader.subprocess, 'run', side_effect=run) as mocked:
                    result = reader.ask_openai_v8('offline prompt')
                mocked.assert_called_once()
                self.assertEqual(result['status'], 'completed')

    def test_arbitrary_key_is_hidden_in_exception_and_http_errors(self):
        key = 'arbitrary-credential-without-prefix'
        os.environ['OPENAI_API_KEY'] = '  ' + key + '\n'
        for outcome in ('exception', 'http'):
            with self.subTest(outcome=outcome):
                def run(argv, **kwargs):
                    if outcome == 'exception':
                        raise RuntimeError('Failed with ' + os.environ['OPENAI_API_KEY'])
                    return subprocess.CompletedProcess(argv, 0,
                        stdout=json.dumps({'error': {'type': key, 'message': key}})
                               + '\n401', stderr='')

                output = io.StringIO()
                with patch.object(reader.subprocess, 'run', side_effect=run), \
                     contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = reader.ask_openai_v8('offline prompt')
                self.assertEqual(result['status'], 'ERROR')
                self.assertNotIn(key, repr(result))
                self.assertEqual(output.getvalue(), '')

    def test_errors_and_redirect_do_not_retry(self):
        for status in (401, 429, 500, 307):
            with self.subTest(status=status):
                result = self.call({'error': {'type': 'api_error',
                    'message': 'offline-key-only Bearer fake-token __SECRET_FAKE__ '
                               'https://user:password@proxy.invalid'}}, status)
                self.assertEqual(result['status'], 'ERROR')
                self.assertEqual(result['error_type'], 'api_error')
                for secret in ('offline-key-only', 'fake-token',
                               '__SECRET_FAKE__', 'user:password'):
                    self.assertNotIn(secret, result['error_message'])

    def test_network_exit_timeout_and_invalid_json(self):
        for kwargs in ({'returncode': 7}, {'raw': 'not JSON'},
                       {'exception': subprocess.TimeoutExpired(['curl'], 65)},
                       {'exception': FileNotFoundError('curl unavailable')}):
            with self.subTest(kwargs=kwargs):
                result = self.call(**kwargs)
                self.assertEqual(result['status'], 'ERROR')
                self.assertIsNone(result['payload'])
                self.assertNotIn('secret stderr', result['error_message'])

    def test_incomplete_and_schema_errors_preserve_raw_and_usage(self):
        for overrides in ({'status': 'incomplete'},
                          {'output_text': '{"final_text":123}'},
                          {'output_text': 'broken JSON'}):
            with self.subTest(overrides=overrides):
                data = self.response(**overrides)
                result = self.call(data)
                self.assertEqual(result['status'], data['status'])
                self.assertEqual(result['usage']['total_tokens'], 18)
                self.assertEqual(result['raw_response_text'],
                    data.get('output_text', '{"final_text":"offline text"}'))
                if 'output_text' in overrides:
                    self.assertTrue(result['issues'])

    def test_default_transport_does_not_invoke_curl(self):
        for selection in (None, 'sdk', 'CURL'):
            with self.subTest(selection=selection):
                if selection is None:
                    os.environ.pop('OPENAI_TRANSPORT', None)
                else:
                    os.environ['OPENAI_TRANSPORT'] = selection
                with patch.object(reader.subprocess, 'run',
                                  side_effect=AssertionError('curl forbidden')) as mocked:
                    # SDK construction is blocked by setUp; no HTTP request occurs.
                    result = reader.ask_openai_v8('offline prompt')
                mocked.assert_not_called()
                self.assertEqual(result['error_message'], 'SDK forbidden in curl mode')


if __name__ == '__main__':
    unittest.main()
