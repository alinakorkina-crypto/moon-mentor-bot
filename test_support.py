"""Offline persistence, concurrency and Telegram support integration."""
import asyncio
import io
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from payments_service import PaymentsService, PaymentError
from support_service import SupportService, PROMPT, LIMIT
import test_bot_reading_integration as integration


class SupportLedgerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'ledger.sqlite3')
        self.payments = PaymentsService(self.path)
        self.support = SupportService(self.payments)

    async def ticket(self, key=(77, 2), user=77):
        await self.support.start(user, key[0])
        return await self.support.submit(key, user, 'person', 'Person', 'Покупка не отобразилась', {11, 22})

    async def test_session_and_ticket_survive_reopen_without_flag_or_secret(self):
        self.assertEqual(await self.support.start(77, 77), PROMPT)
        reopened = SupportService(PaymentsService(self.path))
        self.assertTrue(await reopened.waiting(77, 77))
        number, outgoing = await reopened.submit((77, 2), 77, '', 'Person', 'Не вижу покупку', {11})
        self.assertRegex(number, r'^[A-F0-9]{10}$')
        self.assertEqual(len(outgoing), 1)
        self.assertFalse(await self.support.waiting(77, 77))
        self.assertEqual((await self.support.open_tickets())[0]['number'], number)

    async def test_concurrent_duplicate_creates_one_ticket_and_notification_set(self):
        await self.support.start(77, 77)
        results = await asyncio.gather(*[self.support.submit((77, 2), 77, '', '', 'Нет покупки', {11, 22}) for _ in range(12)])
        self.assertEqual(len({r[0] for r in results}), 1)
        self.assertEqual(sum(len(r[1]) for r in results), 2)
        self.assertEqual(await self.support.count(), 1)

    async def test_one_open_and_cooldown(self):
        number, _ = await self.ticket()
        self.assertIn(number, await self.support.start(77, 77))
        await self.support.act((11, 4), number)
        await self.support.start(77, 77)
        with self.assertRaisesRegex(PaymentError, 'Подождите'):
            await self.support.submit((77, 5), 77, '', '', 'Другая проблема', {})
        with patch('support_service.time.time', return_value=9999999999):
            other, _ = await self.support.submit((77, 6), 77, '', '', 'Другая проблема', {})
        self.assertNotEqual(number, other)

    async def test_concurrent_reply_claim_and_close_idempotence(self):
        number, _ = await self.ticket()
        results = await asyncio.gather(*[self.support.act((11, 10), number, reply='Проверяем') for _ in range(10)])
        self.assertEqual(sum(map(len, results)), 1)
        self.assertEqual([m[1] for result in results for m in result], [77])
        closed = await self.support.act((11, 11), number)
        self.assertEqual(len(closed), 1)
        self.assertEqual(await self.support.act((11, 11), number), [])
        for kwargs in ({}, {'reply': 'Ещё ответ'}):
            with self.assertRaises(PaymentError):
                await self.support.act((11, 12), number, **kwargs)
        self.assertEqual(await self.support.count(), 0)

    async def test_invalid_unknown_number_and_length(self):
        number, _ = await self.ticket()
        for invalid in ('1', '../../test', 'F'*10):
            with self.assertRaises(PaymentError):
                await self.support.act((11, 5), invalid, reply='Текст')
        for text in ('', 'x'*(LIMIT+1)):
            with self.assertRaises(PaymentError):
                await self.support.act((11, 6), number, reply=text)
        await self.support.act((11, 7), number, reply='x'*LIMIT)

    async def test_sensitive_data_never_persisted(self):
        await self.support.start(77, 77)
        for index, text in enumerate(('sk-offline-example', 'Bearer offline-value', '__SECRET_EXAMPLE__',
                                      '4111 1111 1111 1111', 'mm1.offline.invoice', '123456:offline-token')):
            with self.assertRaises(PaymentError):
                await self.support.submit((77, index), 77, '', '', text, {11})
        self.assertEqual(await self.support.count(), 0)
        async with self.payments.transaction() as db:
            row = await self.payments._one(db, 'SELECT COUNT(*) AS n FROM support_messages')
            self.assertEqual(row['n'], 0)

    async def test_commit_failure_prevents_delivery_claim(self):
        import aiosqlite
        number, _ = await self.ticket()
        with patch.object(aiosqlite.Connection, 'commit', side_effect=aiosqlite.OperationalError('offline')):
            with self.assertRaises(PaymentError):
                await self.support.act((11, 99), number, reply='Ответ')
        self.assertEqual(len(await self.support.act((11, 99), number, reply='Ответ')), 1)


class SupportBotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = integration.BotReadingTests()
        self.fixture.extra_environment = {'PAYMENTS_ENABLED': 'false', 'ADMIN_IDS': '11,22',
            'READING_ENGINE': 'v8', 'PAYMENTS_DB_PATH': str(Path(self.tmp.name) / 'payments.sqlite3')}
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bot = self.fixture.bot
        self.bot.update_analytics = AsyncMock(side_effect=AssertionError('Support analytics forbidden'))
        self.send = AsyncMock()
        self.patcher = patch.object(self.bot.bot, 'send_message', self.send)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.support = SupportService(self.bot.payments_service)

    async def asyncTearDown(self):
        await self.bot.bot.session.close()

    def message(self, text, mid=1, user=77):
        msg = self.fixture.message(text, chat_id=user, message_id=mid)
        msg.from_user.id = user
        return msg

    async def create(self):
        await self.bot.handle_buttons(self.message('/paysupport'))
        msg = self.message('Не вижу покупку <b>текст</b>', 2)
        await self.bot.handle_buttons(msg)
        number = (await self.support.open_tickets())[0]['number']
        return number, msg

    async def test_creation_only_admins_plain_text_no_models_analytics(self):
        self.bot.user_mode[77] = 'question'
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger().addHandler(handler)
        try:
            number, msg = await self.create()
        finally:
            logging.getLogger().removeHandler(handler)
        self.assertEqual(msg.answer.call_args.args[0], f'Обращение №{number} передано. Ответ придёт сюда, в Moon Mentor.')
        self.assertEqual({call.args[0] for call in self.send.call_args_list}, self.bot.ADMIN_IDS)
        for call in self.send.call_args_list:
            self.assertIsNone(call.kwargs['parse_mode'])
            self.assertIn('<b>текст</b>', call.args[1])
        self.assertNotIn('покупку', stream.getvalue())
        self.fixture.model.assert_not_called()
        self.bot.ask_gemini.assert_not_called()
        self.bot.draw_cards.assert_not_called()
        self.bot.save_history.assert_not_called()
        self.bot.update_analytics.assert_not_called()
        self.assertIsNone(self.bot.user_mode[77])
        self.assertIs(msg.answer.call_args.kwargs['reply_markup'], self.bot.main_menu)
        previous = self.send.call_count
        await self.bot.handle_buttons(msg)
        self.assertEqual(self.send.call_count, previous)

    async def test_reply_saved_before_delivery_and_repeated_after_reopen(self):
        number, _ = await self.create()
        self.send.reset_mock()
        async def check_saved(recipient, text, **kwargs):
            self.assertEqual(recipient, 77)
            async with self.bot.payments_service.transaction() as db:
                row = await self.bot.payments_service._one(db, "SELECT status FROM support_messages WHERE recipient=77")
                self.assertEqual(row['status'], 'claimed')
            self.assertEqual(text, f'Ответ поддержки по обращению №{number}\n\nПроверяем <i>оплату</i>')
        self.send.side_effect = check_saved
        cmd = self.message(f'/replyticket {number} Проверяем <i>оплату</i>', 10, 11)
        await self.bot.handle_buttons(cmd)
        self.bot.payments_service = PaymentsService(self.bot.payments_service.path)
        await self.bot.handle_buttons(cmd)
        self.send.assert_awaited_once()

    async def test_delivery_failure_no_resend_and_close_idempotent(self):
        number, _ = await self.create()
        self.send.reset_mock()
        self.send.side_effect = RuntimeError('offline failure')
        cmd = self.message(f'/replyticket {number} Проверяем', 10, 11)
        await self.bot.handle_buttons(cmd)
        await self.bot.handle_buttons(cmd)
        self.send.assert_awaited_once()
        self.send.side_effect = None
        close = self.message(f'/closeticket {number}', 11, 11)
        await self.bot.handle_buttons(close)
        await self.bot.handle_buttons(close)
        self.assertEqual(self.send.call_count, 2)
        self.assertEqual(self.send.call_args.args, (77, f'Обращение №{number} закрыто.'))
        async with self.bot.payments_service.transaction() as db:
            row = await self.bot.payments_service._one(db, "SELECT status FROM support_messages WHERE recipient=77 ORDER BY id LIMIT 1")
            self.assertEqual(row['status'], 'uncertain')

    async def test_unauthorized_unknown_and_closed_safe(self):
        number, _ = await self.create()
        self.send.reset_mock()
        for text in (f'/replyticket {number} Ответ', f'/closeticket {number}', '/tickets'):
            msg = self.message(text, 10, 99)
            await self.bot.handle_buttons(msg)
            self.assertEqual(msg.answer.call_args.args[0], 'Команда недоступна.')
        msg = self.message('/replyticket AAAAAAAAAA Ответ', 11, 11)
        await self.bot.handle_buttons(msg)
        self.assertIn('недоступно', msg.answer.call_args.args[0])
        self.send.assert_not_called()

    async def test_tickets_admin_only_diag_count_without_content(self):
        await self.create()
        msg = self.message('/tickets', 12, 11)
        await self.bot.handle_buttons(msg)
        self.assertIn('Не вижу покупку', msg.answer.call_args.args[0])
        msg = self.message('/paymentdiag', 13, 11)
        await self.bot.handle_buttons(msg)
        self.assertIn('Открытых обращений: 1', msg.answer.call_args.args[0])
        self.assertNotIn('Не вижу покупку', msg.answer.call_args.args[0])

    async def test_long_text_keeps_waiting_and_navigation_cancels(self):
        await self.bot.handle_buttons(self.message('/paysupport'))
        msg = self.message('x'*1501, 2)
        await self.bot.handle_buttons(msg)
        self.assertIn('1500', msg.answer.call_args.args[0])
        self.assertTrue(await self.support.waiting(77, 77))
        await self.bot.handle_buttons(self.message('⬅️ Главное меню', 3))
        self.assertFalse(await self.support.waiting(77, 77))
        self.fixture.model.assert_not_called()

    async def test_group_support_does_not_publish_private_content(self):
        msg = self.message('/tickets', 1, 11)
        msg.chat.type = 'supergroup'
        await self.bot.handle_buttons(msg)
        self.assertIn('личный чат', msg.answer.call_args.args[0])
        self.send.assert_not_called()

    async def test_failed_admin_notification_is_not_repeated(self):
        self.send.side_effect = RuntimeError('offline')
        number, msg = await self.create()
        self.assertEqual(await self.support.count(), 1)
        self.assertEqual(self.send.call_count, len(self.bot.ADMIN_IDS))
        await self.bot.handle_buttons(msg)
        self.assertEqual(self.send.call_count, len(self.bot.ADMIN_IDS))
        self.assertIn(number, msg.answer.call_args.args[0])

    async def test_user_receipt_failure_never_runs_reading_on_retry(self):
        await self.bot.handle_buttons(self.message('/paysupport'))
        msg = self.message('Не вижу оплату', 2)
        msg.answer.side_effect = RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            await self.bot.handle_buttons(msg)
        msg.answer.side_effect = None
        await self.bot.handle_buttons(msg)
        self.assertEqual(await self.support.count(), 1)
        self.assertEqual(self.send.call_count, len(self.bot.ADMIN_IDS))
        self.fixture.model.assert_not_called()
        self.bot.ask_gemini.assert_not_called()

    async def test_nontext_pending_does_not_enter_reading(self):
        await self.bot.handle_buttons(self.message('/paysupport'))
        msg = self.message(None, 2)
        await self.bot.handle_buttons(msg)
        self.assertIn('текстом', msg.answer.call_args.args[0])
        self.fixture.model.assert_not_called()
