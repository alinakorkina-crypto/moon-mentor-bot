"""Telegram handler integration with in-memory Telegram/Vertex substitutes."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import ai_reader_openai_v8 as transport
import reading_engine_v8 as engine
import reading_service_v8 as service
from test_reading_engine_v8 import INITIATIVE_CARDS, VALID_INITIATIVE_TEXT


class BotReadingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guards = []
        for target in ('socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.create_connection', 'subprocess.run'):
            guard = patch(target, side_effect=AssertionError('External IO forbidden'))
            guard.start()
            self.addCleanup(guard.stop)
        environment = patch.dict(os.environ, {'BOT_TOKEN': 'offline-token'}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

        # aiogram/google-genai are not installed in this workspace. Execute the
        # real main.py handlers with inert Telegram types and a fake Vertex client.
        aiogram = types.ModuleType('aiogram')
        aiogram.Bot = Mock()
        dispatcher = MagicMock()
        dispatcher.message.return_value = lambda function: function
        aiogram.Dispatcher = Mock(return_value=dispatcher)
        telegram_types = types.ModuleType('aiogram.types')
        for name in ('Message', 'ReplyKeyboardMarkup', 'KeyboardButton',
                     'FSInputFile', 'InputMediaPhoto'):
            setattr(telegram_types, name, MagicMock())
        filters = types.ModuleType('aiogram.filters')
        filters.CommandStart = Mock()
        legacy = types.ModuleType('ai_reader')
        legacy.ask_gemini = Mock(return_value=None)
        spec = importlib.util.spec_from_file_location('offline_bot', Path('main.py'))
        self.bot = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'aiogram': aiogram, 'aiogram.types': telegram_types,
                                     'aiogram.filters': filters, 'ai_reader': legacy}), \
             patch('dotenv.load_dotenv') as load:
            spec.loader.exec_module(self.bot)
            load.assert_called_once()
        self.bot.ask_gemini = Mock(side_effect=AssertionError('Gemini forbidden'))
        self.actual_save_history = self.bot.save_history
        self.bot.save_history = Mock()
        self.bot.draw_cards = Mock(return_value=INITIATIVE_CARDS)
        self.model = Mock(return_value={'payload': {'final_text': VALID_INITIATIVE_TEXT},
                                        'status': 'completed'})
        guard = patch.object(transport, 'ask_openai_v8', self.model)
        guard.start()
        self.addCleanup(guard.stop)

    def message(self, text='Что мне важно понять сейчас?', *, chat_id=100, message_id=20):
        return types.SimpleNamespace(
            text=text, chat=types.SimpleNamespace(id=chat_id), message_id=message_id,
            from_user=types.SimpleNamespace(id=77, username='offline_user'),
            answer=AsyncMock(), answer_photo=AsyncMock(), answer_media_group=AsyncMock(),
        )

    async def run_mode(self, mode, text='Что мне важно понять сейчас?', *, message_id=20):
        message = self.message(text, message_id=message_id)
        self.bot.user_mode[77] = mode
        await self.bot.handle_buttons(message)
        return message

    async def test_absent_or_legacy_flag_preserves_old_function_and_result(self):
        for flag in (None, 'legacy'):
            for mode in ('question', 'love', 'career'):
                with self.subTest(flag=flag, mode=mode):
                    if flag is None:
                        os.environ.pop('READING_ENGINE', None)
                    else:
                        os.environ['READING_ENGINE'] = flag
                    function = {'question': 'make_question_reading',
                                'love': 'make_love_reading', 'career': 'make_career_reading'}[mode]
                    with patch.object(self.bot, function, return_value=('legacy unchanged', INITIATIVE_CARDS)) as old, \
                         patch.object(self.bot, 'send_reading', new_callable=AsyncMock) as send:
                        message = await self.run_mode(mode)
                    old.assert_called_once_with(message.text, 77, '@offline_user')
                    send.assert_awaited_once_with(message, 'legacy unchanged', INITIATIVE_CARDS,
                                                 reply_markup=self.bot.main_menu)
        self.model.assert_not_called()

    async def test_exact_question_topic_cards_and_one_call_for_all_three_modes(self):
        os.environ['READING_ENGINE'] = 'v8'
        original = engine.generate_reading_v8
        worker_threads = []
        def generate(**kwargs):
            worker_threads.append(threading.get_ident())
            return original(**kwargs)
        with patch.object(engine, 'generate_reading_v8', side_effect=generate) as generated:
            for index, (mode, topic) in enumerate(service.MODE_TOPICS.items()):
                question = '  Что мне важно понять сейчас?\n'
                message = await self.run_mode(mode, question, message_id=index)
                kwargs = generated.call_args.kwargs
                self.assertEqual(kwargs['question'], question)
                self.assertEqual(kwargs['topic'], topic)
                self.assertIs(kwargs['cards'], INITIATIVE_CARDS)
                operation = self.bot.reading_service_v8.get((100, index))
                self.assertEqual((await operation.result())['route'], 'open_question')
                self.assertIs(operation.cards, INITIATIVE_CARDS)
                self.assertEqual(self.bot.user_mode[77], None)
                self.assertIn(VALID_INITIATIVE_TEXT, message.answer.call_args.args[0])
            self.assertEqual(generated.call_count, 3)
        self.assertEqual(self.model.call_count, 3)
        self.assertEqual(self.bot.draw_cards.call_count, 3)
        self.assertTrue(all(t != threading.get_ident() for t in worker_threads))
        self.bot.ask_gemini.assert_not_called()

    async def test_all_routes_go_through_v8(self):
        os.environ['READING_ENGINE'] = 'v8'
        for index, (question, route) in enumerate((
            ('Что происходит между нами?', 'open_question'),
            ('Выйдет ли он первым на контакт?', 'initiative'),
            ('Стоит ли продолжать этот контакт?', 'personal_choice'),
        )):
            await self.run_mode('love', question, message_id=index)
            result = await self.bot.reading_service_v8.get((100, index)).result()
            self.assertEqual(result['route'], route)
            self.assertEqual(result['status'], 'success')
        self.assertEqual(self.model.call_count, 3)

    async def test_text_headers_cards_images_keyboard_history_and_warnings(self):
        os.environ['READING_ENGINE'] = 'v8'
        raw = '  ' + VALID_INITIATIVE_TEXT.replace('\n\n', ' ') + '  '
        self.model.return_value = {'payload': {'final_text': raw}, 'status': 'completed'}
        for index, mode in enumerate(('question', 'love', 'career')):
            with patch.object(self.bot, 'cleanup_generated_text', side_effect=AssertionError('cleanup forbidden')), \
                 patch.object(self.bot, 'validate_final_answer', side_effect=AssertionError('validation forbidden')), \
                 patch.object(self.bot, 'make_v13_tarot_reading', side_effect=AssertionError('legacy forbidden')), \
                 patch.object(self.bot.os.path, 'exists', return_value=True):
                message = await self.run_mode(mode, message_id=index)
            sent = message.answer.call_args.args[0]
            heading = {'question': f'💭 Ваш вопрос\n\n{message.text}',
                       'love': '❤️ Расклад на отношения', 'career': '💼 Карьерный расклад'}[mode]
            self.assertEqual(sent, heading + '\n\n🃏 Выпавшие карты\n\n' +
                             self.bot.format_cards_list(INITIATIVE_CARDS) + '\n\n' + raw)
            self.assertIs(message.answer.call_args.kwargs['reply_markup'], self.bot.main_menu)
            message.answer_media_group.assert_awaited_once()
            self.assertEqual(self.bot.InputMediaPhoto.call_args_list[-3:], [
                unittest.mock.call(media=self.bot.FSInputFile.return_value)] * 3)
            image_paths = [c.args[0] for c in self.bot.FSInputFile.call_args_list[-3:]]
            self.assertEqual(image_paths, ['cards/chariot.jpg', 'cards/tower.jpg', 'cards/star.jpg'])
            operation = self.bot.reading_service_v8.get((100, index))
            self.assertTrue((await operation.result())['warnings'])
            self.bot.save_history.assert_called_with(77,
                {'question': 'personal_question', 'love': 'love', 'career': 'career'}[mode],
                INITIATIVE_CARDS, question=message.text, username='@offline_user')
        self.assertEqual(self.bot.save_history.call_count, 3)
        self.bot.ask_gemini.assert_not_called()

    async def test_failures_are_neutral_and_cached_without_history_or_fallback(self):
        os.environ['READING_ENGINE'] = 'v8'
        outcomes = (
            {'status': 'ERROR', 'error_message': 'private details'},
            {'payload': {'final_text': 'Он хочет написать первым.'}},
            TimeoutError('private timeout'), '{',
        )
        for index, outcome in enumerate(outcomes):
            with self.subTest(index=index):
                self.model.reset_mock(side_effect=True)
                if isinstance(outcome, Exception):
                    self.model.side_effect = outcome
                else:
                    self.model.return_value = outcome
                message = await self.run_mode('question', message_id=index)
                await self.bot.handle_buttons(message)
                self.model.assert_called_once()
                self.assertEqual([c.args[0] for c in message.answer.call_args_list],
                                 ['🃏 Раскладываю карты...', service.FAILURE_MESSAGE])
                message.answer_media_group.assert_not_awaited()
                message.answer_photo.assert_not_awaited()
        self.bot.save_history.assert_not_called()
        self.bot.ask_gemini.assert_not_called()

    async def test_redelivery_after_telegram_failure_reuses_success(self):
        os.environ['READING_ENGINE'] = 'v8'
        message = self.message()
        self.bot.user_mode[77] = 'question'
        message.answer.side_effect = [None, RuntimeError('Telegram unavailable')]
        with self.assertRaises(RuntimeError):
            await self.bot.handle_buttons(message)
        operation = self.bot.reading_service_v8.get((100, 20))
        self.assertEqual((await operation.result())['status'], 'success')
        message.answer.side_effect = None
        # Cache wins even after feature flag and navigation state change.
        os.environ['READING_ENGINE'] = 'legacy'
        await self.bot.handle_buttons(message)
        await self.bot.handle_buttons(message)
        self.model.assert_called_once()
        self.bot.draw_cards.assert_called_once_with(3)
        self.bot.save_history.assert_called_once()
        self.assertTrue(operation.delivered)

    async def test_concurrent_redelivery_generates_and_delivers_once(self):
        os.environ['READING_ENGINE'] = 'v8'
        message = self.message()
        self.bot.user_mode[77] = 'question'
        await asyncio.gather(self.bot.handle_buttons(message), self.bot.handle_buttons(message))
        self.model.assert_called_once()
        self.bot.draw_cards.assert_called_once_with(3)
        self.assertEqual(message.answer.await_count, 2)

    async def test_chat_id_is_part_of_operation_key(self):
        os.environ['READING_ENGINE'] = 'v8'
        for chat_id in (100, 200):
            self.bot.user_mode[77] = 'question'
            await self.bot.handle_buttons(self.message(chat_id=chat_id))
        self.assertEqual(self.model.call_count, 2)

    async def test_day_full_and_chat_keep_legacy_path_under_v8(self):
        os.environ['READING_ENGINE'] = 'v8'
        self.bot.ask_gemini.side_effect = None
        self.bot.ask_gemini.return_value = 'legacy AI text'
        with patch.object(self.bot, 'send_reading', new_callable=AsyncMock) as send, \
             patch.object(self.bot, 'validate_final_answer', return_value='legacy validated') as validate, \
             patch.object(self.bot, 'send_text', new_callable=AsyncMock) as send_text:
            await self.bot.handle_buttons(self.message('🃏 Карта дня'))
            self.assertEqual(len(send.call_args.args[2]), 1)
            self.bot.draw_cards.assert_not_called()
            four_cards = INITIATIVE_CARDS + [{'name': 'Солнце', 'general': 'Тепло',
                                             'advice': 'Наблюдайте', 'question': 'Что видно?'}]
            self.bot.draw_cards.return_value = four_cards
            await self.bot.handle_buttons(self.message('🌙 Полный расклад'))
            self.bot.draw_cards.assert_called_once_with(4)
            self.assertIs(send.call_args.args[2], four_cards)
            self.assertIn('legacy validated', send.call_args.args[1])
            validate.assert_called_once()
            self.bot.user_mode[77] = 'chat'
            await self.bot.handle_buttons(self.message('Хочу поговорить'))
            send_text.assert_awaited_once()
            self.assertEqual(self.bot.ask_gemini.call_count, 2)
        self.model.assert_not_called()

    async def test_navigation_and_start_remain_unchanged(self):
        os.environ['READING_ENGINE'] = 'v8'
        message = self.message('⬅️ Главное меню')
        self.bot.user_mode[77] = 'love'
        await self.bot.handle_buttons(message)
        self.assertIsNone(self.bot.user_mode[77])
        self.assertIs(message.answer.call_args.kwargs['reply_markup'], self.bot.main_menu)
        await self.bot.start_command(message)
        self.assertIn('Добро пожаловать в Moon Mentor', message.answer.call_args.args[0])
        self.model.assert_not_called()

    async def test_history_and_analytics_written_once_for_success_only(self):
        os.environ['READING_ENGINE'] = 'v8'
        with tempfile.TemporaryDirectory() as directory:
            self.bot.HISTORY_FILE = str(Path(directory) / 'history.json')
            self.bot.ANALYTICS_FILE = str(Path(directory) / 'analytics.json')
            self.bot.DIALOGS_FILE = str(Path(directory) / 'dialogs.jsonl')
            self.bot.save_history = self.actual_save_history
            message = await self.run_mode('love')
            await self.bot.handle_buttons(message)
            self.model.return_value = {'status': 'ERROR'}
            await self.run_mode('career', message_id=21)
            history = json.loads(Path(self.bot.HISTORY_FILE).read_text())
            analytics = json.loads(Path(self.bot.ANALYTICS_FILE).read_text())
            self.assertEqual(len(history['77']), 1)
            self.assertEqual(history['77'][0]['type'], 'love')
            self.assertEqual(history['77'][0]['question'], message.text)
            self.assertEqual(history['77'][0]['cards'], [c['name'] for c in INITIATIVE_CARDS])
            self.assertEqual(analytics['total_readings'], 1)
            self.assertEqual(len(Path(self.bot.DIALOGS_FILE).read_text().splitlines()), 1)

    async def test_configuration_is_loaded_before_adapter_creation(self):
        import ast
        tree = ast.parse(Path('main.py').read_text())
        dotenv_line = next(n.lineno for n in tree.body if isinstance(n, ast.Expr)
                           and isinstance(n.value, ast.Call)
                           and isinstance(n.value.func, ast.Name)
                           and n.value.func.id == 'load_dotenv')
        adapter_import_line = next(n.lineno for n in tree.body if isinstance(n, ast.ImportFrom)
                                   and n.module == 'reading_service_v8')
        self.assertLess(dotenv_line, adapter_import_line)

    async def test_missing_image_files_do_not_prevent_v8_text_delivery(self):
        os.environ['READING_ENGINE'] = 'v8'
        with patch.object(self.bot.os.path, 'exists', return_value=False):
            message = await self.run_mode('question')
        message.answer_media_group.assert_not_awaited()
        message.answer_photo.assert_not_awaited()
        self.assertIn(VALID_INITIATIVE_TEXT, message.answer.call_args.args[0])
        self.model.assert_called_once()


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_waiter_does_not_restart_generation(self):
        adapter = service.ReadingServiceV8()
        ready = asyncio.Event()
        async def run(*args):
            await ready.wait()
            return {'status': 'success', 'text': 'cached'}
        with patch.object(service, '_run', side_effect=run) as generate:
            operation = adapter.start((1, 2), mode='question', question='q', cards=INITIATIVE_CARDS)
            waiter = asyncio.create_task(operation.result())
            await asyncio.sleep(0)
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            self.assertIs(adapter.start((1, 2), mode='question', question='q', cards=[]), operation)
            ready.set()
            self.assertEqual((await operation.result())['text'], 'cached')
            generate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
