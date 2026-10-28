"""Production dependencies and release boundaries; no live requests."""
import ast
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from aiogram import Bot, Dispatcher
from google import genai

import reading_engine_v8 as engine
import reading_service_v8 as service


class ReleaseCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_import_legacy_and_v8_without_polling(self):
        for flag in ('legacy', 'v8'):
            with self.subTest(flag=flag), \
                 patch.dict(os.environ, {'BOT_TOKEN': '123456:offline-test-token',
                                         'OPENAI_API_KEY': 'offline-test-only',
                                         'READING_ENGINE': flag}, clear=True), \
                 patch('dotenv.load_dotenv'), \
                 patch.object(Dispatcher, 'start_polling', new_callable=AsyncMock) as polling:
                spec = importlib.util.spec_from_file_location('release_import_check', Path('main.py'))
                bot_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(bot_module)
                self.assertIsInstance(bot_module.bot, Bot)
                self.assertIsInstance(bot_module.dp, Dispatcher)
                self.assertIsInstance(bot_module.ask_gemini.__globals__['client'], genai.Client)
                self.assertEqual(service.v8_enabled(), flag == 'v8')
                polling.assert_not_awaited()
                await bot_module.bot.session.close()

    async def test_default_is_legacy_and_sdk_transport_is_available(self):
        import httpx
        from openai import OpenAI
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(service.v8_enabled())
        with httpx.Client(transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(AssertionError('No request expected')))) as http_client:
            with OpenAI(api_key='offline-test-only', max_retries=0,
                        http_client=http_client) as client:
                self.assertTrue(callable(client.responses.create))

    async def test_no_experimental_files_or_imports(self):
        import re
        for path in Path('.').glob('*.py'):
            self.assertIsNone(re.match(r'(?:preview_reading_v\d|ai_reader_v[3-7]|reading_engine_v[2-7]|test_reading_engine_v[2-7])', path.name))
            for node in ast.walk(ast.parse(path.read_text())):
                names = [node.module or ''] if isinstance(node, ast.ImportFrom) else \
                        [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
                for name in names:
                    self.assertIsNone(re.match(r'(?:reading_engine_v[2-7]|ai_reader_v[3-7]|preview_reading_v\d)', name))
        self.assertFalse(Path('AGENTS.md').exists())

    async def test_name_matching_and_layout_keep_final_behavior(self):
        cards = [{'name': 'Колесница'}, {'name': 'Башня'}, {'name': 'Звезда'}]
        for text in ('Колесница Башня Звезда', 'Колесницей Башней Звездой',
                     'Кoлесница Башня Звездa', 'Колесница Ба\u200bшня Звезда'):
            with self.subTest(text=text):
                self.assertEqual(engine.missing_cards_v8(text, cards), [])
        self.assertEqual(engine.normalize_final_layout_v8('один\\n\\nдва\\n\\nтри'),
                         'один\n\nдва\n\nтри')
        self.assertEqual(engine.count_words_v8('один два-три 123'), 3)


if __name__ == '__main__':
    unittest.main()
