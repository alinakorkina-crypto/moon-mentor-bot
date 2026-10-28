"""Offline Stars handlers and full v8 credit lifecycle, using real aiogram."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import AsyncMock, patch

import test_bot_reading_integration as bot_tests
from test_reading_engine_v8 import VALID_INITIATIVE_TEXT
from payments_readings import PaidReadings
from reading_service_v8 import ReadingServiceV8
from payments_service import PACKAGES


class PaymentsBotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture = bot_tests.BotReadingTests()
        self.fixture.extra_environment = {
            'PAYMENTS_ENABLED': 'true', 'READING_ENGINE': 'v8',
            'PAYMENT_PAYLOAD_SECRET': 'offline-payload-signing-secret',
            'PAYMENTS_DB_PATH': str(Path(self.directory.name)/'payments.sqlite3'),
            'ADMIN_IDS': '77',
        }
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bot = self.fixture.bot
        self.service = self.bot.payments_service
        self.model = self.fixture.model

    async def asyncTearDown(self):
        await self.bot.bot.session.close()

    async def run_mode(self, mode='question', message_id=20):
        return await self.fixture.run_mode(mode, message_id=message_id)

    async def purchase(self, package='moon_1', charge='offline-charge'):
        invoice = await self.service.issue_invoice(77, package)
        await self.service.credit_purchase(77, invoice['payload'], 'XTR', invoice['stars'], charge)
        return invoice

    async def test_three_successes_then_fourth_blocked_before_draw_and_ai(self):
        for index, mode in enumerate(('question','love','career')):
            message = await self.run_mode(mode, index)
            self.assertIn(VALID_INITIATIVE_TEXT, message.answer.call_args.args[0])
        self.assertEqual((await self.service.balance(77)).free, 0)
        fourth = await self.run_mode(message_id=4)
        self.assertIn('Бесплатные расклады закончились', fourth.answer.call_args.args[0])
        self.assertEqual(len(fourth.answer.call_args.kwargs['reply_markup'].inline_keyboard), 3)
        self.assertEqual(self.bot.draw_cards.call_count, 3)
        self.assertEqual(self.model.call_count, 3)
        self.assertEqual(self.bot.save_history.call_count, 3)
        self.assertEqual((await self.service.statistics())['free'], 3)

    async def test_completion_is_committed_before_telegram_text(self):
        message = self.fixture.message()
        self.bot.user_mode[77] = 'question'
        async def answer(text, **kwargs):
            # In the paid path even the progress notification occurs only after
            # a durable completed result, so no send can consume a second credit.
            stats = await self.service.statistics()
            self.assertEqual(stats['free'], 1)
            row, new = await self.service.reserve((100,20),77)
            self.assertFalse(new)
            self.assertEqual(row['status'], 'completed')
            self.assertEqual(VALID_INITIATIVE_TEXT, json.loads(row['result_json'])['text'])
        message.answer.side_effect = answer
        await self.bot.handle_buttons(message)
        self.assertEqual((await self.service.balance(77)).free, 2)

    async def test_error_rejected_timeout_invalid_json_release_once(self):
        for index, outcome in enumerate(({'status':'ERROR'},
            {'payload':{'final_text':'Он хочет написать первым.'}}, TimeoutError('offline'), '{')):
            with self.subTest(index=index):
                self.model.reset_mock(side_effect=True)
                if isinstance(outcome, Exception): self.model.side_effect=outcome
                else: self.model.return_value=outcome
                message = await self.run_mode(message_id=index)
                await self.bot.handle_buttons(message)
                self.model.assert_called_once()
                self.assertEqual((await self.service.balance(77)).free, 3)
                self.assertEqual(message.answer.call_args.args[0], self.bot.FAILURE_MESSAGE)
                row, new = await self.service.reserve((100,index),77)
                self.assertFalse(new)
                self.assertEqual(row['status'],'released')
                await self.service.finish((100,index),success=False)
                self.assertEqual((await self.service.balance(77)).free,3)
        self.bot.ask_gemini.assert_not_called()
        self.bot.save_history.assert_not_called()

    async def test_paid_credits_after_free_and_duplicate_message(self):
        await self.purchase('moon_5')
        for index in range(4):
            message = await self.run_mode(message_id=index)
            await self.bot.handle_buttons(message)
        balance = await self.service.balance(77)
        self.assertEqual((balance.free,balance.paid),(0,4))
        self.assertEqual(self.model.call_count,4)
        self.assertEqual(self.bot.draw_cards.call_count,4)
        self.assertEqual((await self.service.statistics())['paid'],1)

    async def test_telegram_failure_reuses_same_result_without_refund(self):
        message = self.fixture.message()
        self.bot.user_mode[77]='question'
        message.answer.side_effect=[None,RuntimeError('offline Telegram failure')]
        with self.assertRaises(RuntimeError):
            await self.bot.handle_buttons(message)
        self.assertEqual((await self.service.balance(77)).free,2)
        operation=self.bot.reading_service_v8.get((100,20))
        result=await operation.result()
        message.answer.side_effect=None
        await self.bot.handle_buttons(message)
        self.assertIs(await operation.result(),result)
        self.model.assert_called_once()
        self.bot.draw_cards.assert_called_once_with(3)
        self.bot.save_history.assert_called_once()
        self.assertEqual((await self.service.balance(77)).free,2)

    async def test_cancelled_handler_finalizes_success_or_error(self):
        for index, success in enumerate((True,False)):
            started, release = threading.Event(), threading.Event()
            def model(prompt):
                started.set()
                release.wait(timeout=3)
                return {'payload':{'final_text':VALID_INITIATIVE_TEXT}} if success else '{'
            self.model.side_effect=model
            message=self.fixture.message(message_id=index)
            self.bot.user_mode[77]='question'
            handler=asyncio.create_task(self.bot.handle_buttons(message))
            self.assertTrue(await asyncio.to_thread(started.wait,2))
            handler.cancel()
            with self.assertRaises(asyncio.CancelledError): await handler
            self.assertEqual((await self.service.balance(77)).free,2 if index==0 else 1)
            self.assertEqual((await self.service.statistics())['free'], index)
            release.set()
            await self.bot.paid_readings.tasks[(100,index)]
            self.assertEqual((await self.service.balance(77)).free,2)
            row,_=await self.service.reserve((100,index),77)
            self.assertEqual(row['status'],'completed' if success else 'released')
        self.assertEqual(self.model.call_count,2)

    async def test_concurrent_duplicate_cannot_generate_or_reserve_twice(self):
        message=self.fixture.message()
        self.bot.user_mode[77]='question'
        await asyncio.gather(self.bot.handle_buttons(message),self.bot.handle_buttons(message))
        self.model.assert_called_once()
        self.bot.draw_cards.assert_called_once_with(3)
        self.assertEqual((await self.service.balance(77)).free,2)

    async def test_completed_result_restored_after_process_cache_loss(self):
        message=await self.run_mode()
        self.bot.reading_service_v8=ReadingServiceV8()
        self.bot.paid_readings=PaidReadings(self.service,self.bot.reading_service_v8,self.bot.draw_cards)
        # Simulate a delivery retry with no in-process cache, then inspect the
        # durable result. The message is already delivered, so no output repeats.
        self.bot.user_mode[77]='question'
        count=message.answer.await_count
        await self.bot.handle_buttons(message)
        self.assertEqual(message.answer.await_count,count)
        self.model.assert_called_once()
        self.bot.draw_cards.assert_called_once()
        self.bot.save_history.assert_called_once()

    async def test_invoice_packages_xtr_without_provider_token(self):
        for package,(stars,credits) in PACKAGES.items():
            message=self.fixture.message()
            message.answer_invoice=AsyncMock()
            callback=types.SimpleNamespace(data='moon_buy:'+package,
                from_user=message.from_user,message=message,answer=AsyncMock())
            await self.bot.buy_package(callback)
            callback.answer.assert_awaited_once()
            kwargs=message.answer_invoice.call_args.kwargs
            self.assertEqual(kwargs['currency'],'XTR')
            self.assertNotIn('provider_token',kwargs)
            self.assertEqual(kwargs['prices'][0].amount,stars)
            self.assertEqual(await self.service.validate_checkout(77,kwargs['payload'],'XTR',stars),package)

    async def test_precheckout_answers_once_and_rejects_invalid_values(self):
        invoice=await self.service.issue_invoice(77,'moon_1')
        for currency,amount,payload,user,ok in (
            ('XTR',50,invoice['payload'],77,True),('USD',50,invoice['payload'],77,False),
            ('XTR',51,invoice['payload'],77,False),('XTR',50,'broken',77,False),
            ('XTR',50,invoice['payload'],99,False)):
            query=types.SimpleNamespace(from_user=types.SimpleNamespace(id=user),
                id='offline-checkout', currency=currency,total_amount=amount,invoice_payload=payload,answer=AsyncMock())
            await self.bot.checkout_payment(query)
            query.answer.assert_awaited_once()
            self.assertEqual(query.answer.call_args.kwargs['ok'],ok)

    async def test_successful_payment_duplicate_and_invalid_message(self):
        invoice=await self.service.issue_invoice(77,'moon_5')
        message=self.fixture.message()
        message.successful_payment=types.SimpleNamespace(invoice_payload=invoice['payload'],
            currency='XTR',total_amount=200,telegram_payment_charge_id='offline-charge')
        await self.bot.successful_payment(message)
        await self.bot.successful_payment(message)
        self.assertEqual((await self.service.balance(77)).paid,5)
        self.assertIn('Купленные: 5',message.answer.call_args.args[0])
        message.successful_payment.currency='USD'
        await self.bot.successful_payment(message)
        self.assertIn('повторно платить не нужно',message.answer.call_args.args[0])
        self.assertEqual((await self.service.balance(77)).paid,5)

    async def test_real_dispatcher_routes_payment_updates_before_text_catchall(self):
        from datetime import datetime, timezone
        from aiogram.types import Update, PreCheckoutQuery, User, Message, Chat, SuccessfulPayment
        from aiogram.methods import AnswerPreCheckoutQuery, SendMessage
        user = User(id=77, is_bot=False, first_name='Offline')
        invoice = await self.service.issue_invoice(77, 'moon_5')
        query = PreCheckoutQuery(id='offline-checkout', from_user=user,
            currency='XTR', total_amount=200, invoice_payload=invoice['payload'])
        payment = SuccessfulPayment(currency='XTR', total_amount=200,
            invoice_payload=invoice['payload'], telegram_payment_charge_id='offline-router-charge',
            provider_payment_charge_id='')
        message = Message(message_id=1000, date=datetime.now(timezone.utc),
            chat=Chat(id=100, type='private'), from_user=user, successful_payment=payment)
        with patch.object(self.bot.bot.session, 'make_request', new_callable=AsyncMock, return_value=True) as request:
            await self.bot.dp.feed_update(self.bot.bot, Update(update_id=1, pre_checkout_query=query))
            await self.bot.dp.feed_update(self.bot.bot, Update(update_id=2, message=message))
            await self.bot.dp.feed_update(self.bot.bot, Update(update_id=3, message=message))
        methods = [c.args[1] for c in request.call_args_list]
        self.assertIsInstance(methods[0], AnswerPreCheckoutQuery)
        self.assertTrue(methods[0].ok)
        self.assertEqual(sum(isinstance(m, AnswerPreCheckoutQuery) for m in methods), 1)
        self.assertTrue(all(isinstance(m, SendMessage) for m in methods[1:]))
        self.assertEqual((await self.service.balance(77)).paid, 5)
        self.model.assert_not_called()

    async def test_real_dispatcher_creates_xtr_invoice_without_provider_token(self):
        from datetime import datetime, timezone
        from aiogram.types import Update, CallbackQuery, User, Message, Chat
        from aiogram.methods import AnswerCallbackQuery, SendInvoice
        user = User(id=77, is_bot=False, first_name='Offline')
        message = Message(message_id=2000, date=datetime.now(timezone.utc),
            chat=Chat(id=100, type='private'), from_user=user, text='Покупка')
        callback = CallbackQuery(id='offline-buy', from_user=user, chat_instance='offline',
                                 message=message, data='moon_buy:moon_10')
        with patch.object(self.bot.bot.session, 'make_request', new_callable=AsyncMock, return_value=True) as request:
            await self.bot.dp.feed_update(self.bot.bot, Update(update_id=1, callback_query=callback))
        methods = [c.args[1] for c in request.call_args_list]
        self.assertIsInstance(methods[0], AnswerCallbackQuery)
        self.assertIsInstance(methods[1], SendInvoice)
        self.assertEqual(methods[1].currency, 'XTR')
        self.assertEqual(methods[1].prices[0].amount, 350)
        self.assertNotIn('provider_token', methods[1].model_dump(exclude_none=True))
        self.model.assert_not_called()

    async def test_balance_support_and_menus(self):
        await self.purchase('moon_5')
        for text in ('/balance','🌙 Мой баланс'):
            message=self.fixture.message(text)
            await self.bot.handle_buttons(message)
            answer=message.answer.call_args.args[0]
            self.assertIn('Бесплатные: 3',answer)
            self.assertIn('Купленные: 5',answer)
            self.assertIn('Всего доступно: 8',answer)
        message=self.fixture.message('/paysupport')
        self.bot.user_mode[77] = 'question'
        await self.bot.handle_buttons(message)
        self.assertIsNone(self.bot.user_mode[77])
        self.model.assert_not_called()
        self.assertIn('описанием проблемы',message.answer.call_args.args[0])
        with patch.dict(os.environ,{'PAY_SUPPORT_CONTACT':'@offline_support'}):
            await self.bot.handle_buttons(message)
            self.assertIn('@offline_support',message.answer.call_args.args[0])
        self.assertEqual([row[0].text for row in self.bot.main_menu.keyboard[:3]],
                         ['💬 Поговорить с Moon','🔮 Расклад Таро','🌙 О Moon'])
        self.assertEqual([b.text for b in self.bot.main_menu.keyboard[-1]],
                         ['⭐ Купить расклады','🌙 Мой баланс'])

    async def test_refund_admin_only_idempotent_and_pending_not_retried(self):
        await self.purchase('moon_5')
        message=self.fixture.message('/refundstars offline-charge')
        with patch.object(self.bot.bot,'refund_star_payment',new_callable=AsyncMock,return_value=True) as refund:
            message.from_user.id=99
            await self.bot.handle_buttons(message)
            refund.assert_not_awaited()
            message.from_user.id=77
            await self.bot.handle_buttons(message)
            await self.bot.handle_buttons(message)
            refund.assert_awaited_once_with(user_id=77,telegram_payment_charge_id='offline-charge')
        self.assertEqual((await self.service.balance(77)).paid,0)
        await self.purchase(charge='uncertain-charge')
        message.text='/refundstars uncertain-charge'
        with patch.object(self.bot.bot,'refund_star_payment',new_callable=AsyncMock,side_effect=TimeoutError('offline')) as refund:
            await self.bot.handle_buttons(message)
            await self.bot.handle_buttons(message)
            refund.assert_awaited_once()
            self.assertIn('ожидает подтверждения',message.answer.call_args.args[0])

    async def test_statistics_have_only_aggregates(self):
        await self.purchase('moon_5')
        await self.run_mode()
        text=await self.bot.payment_admin_stats()
        self.assertIn('Покупок: 1',text)
        self.assertIn('Получено Stars: 200',text)
        self.assertIn('Выдано платных кредитов: 5',text)
        self.assertIn('Использовано бесплатных: 1',text)
        self.assertNotIn('offline-charge',text)

    async def test_no_credit_to_package_payment_to_new_reading(self):
        for index in range(3):
            await self.run_mode(message_id=index)
        blocked = await self.run_mode(message_id=3)
        self.assertIn('Бесплатные расклады закончились', blocked.answer.call_args.args[0])
        invoice = await self.service.issue_invoice(77, 'moon_1')
        payment_message = self.fixture.message()
        payment_message.successful_payment = types.SimpleNamespace(
            invoice_payload=invoice['payload'], currency='XTR', total_amount=50,
            telegram_payment_charge_id='offline-purchase-path')
        await self.bot.successful_payment(payment_message)
        self.assertEqual((await self.service.balance(77)).paid, 1)
        await self.run_mode(message_id=4)
        self.assertEqual((await self.service.balance(77)).paid, 0)
        self.assertEqual(self.model.call_count, 4)

    async def test_bad_database_and_placeholder_secret_fail_closed(self):
        self.service.path = str(Path(self.directory.name)/'missing'/'ledger.sqlite3')
        message = await self.run_mode(message_id=1)
        self.assertIn('недоступны', message.answer.call_args.args[0])
        self.service._secret = b'__SECRET_OFFLINE_PLACEHOLDER__'
        message = await self.run_mode(message_id=2)
        self.assertIn('недоступны', message.answer.call_args.args[0])
        self.bot.draw_cards.assert_not_called()
        self.model.assert_not_called()

    async def test_checkout_timeout_answered_once_without_accepting(self):
        query = types.SimpleNamespace(from_user=types.SimpleNamespace(id=77),
            id='offline-checkout', invoice_payload='offline', currency='XTR', total_amount=50, answer=AsyncMock())
        with patch.object(self.service, 'validate_checkout', side_effect=TimeoutError):
            await self.bot.checkout_payment(query)
        query.answer.assert_awaited_once()
        self.assertFalse(query.answer.call_args.kwargs['ok'])

    async def test_inflight_payment_can_finish_after_sales_disabled(self):
        invoice = await self.service.issue_invoice(77, 'moon_1')
        self.service.requested = False
        message = self.fixture.message()
        message.successful_payment = types.SimpleNamespace(invoice_payload=invoice['payload'],
            currency='XTR', total_amount=50, telegram_payment_charge_id='offline-inflight')
        await self.bot.successful_payment(message)
        self.assertEqual((await self.service.balance(77)).paid, 1)

    async def test_missing_secret_fails_closed_before_draw(self):
        self.service._secret=b''
        message=await self.run_mode()
        self.model.assert_not_called()
        self.bot.draw_cards.assert_not_called()
        self.assertIn('недоступны',message.answer.call_args.args[0])

    async def test_legacy_and_other_scenarios_do_not_reserve_credits(self):
        with patch.object(self.service,'reserve',side_effect=AssertionError('Reservation forbidden')):
            os.environ['READING_ENGINE']='legacy'
            for mode,function in (('question','make_question_reading'),('love','make_love_reading'),('career','make_career_reading')):
                with patch.object(self.bot,function,return_value=('old',[])), patch.object(self.bot,'send_reading',new_callable=AsyncMock):
                    await self.run_mode(mode)
            os.environ['READING_ENGINE']='v8'
            await self.fixture.test_day_full_and_chat_keep_legacy_path_under_v8()
        self.assertFalse(Path(self.service.path).exists())


class DisabledPaymentTests(unittest.IsolatedAsyncioTestCase):
    async def test_absent_and_false_preserve_v8_without_secret_or_database(self):
        for value in (None, 'false'):
            with tempfile.TemporaryDirectory() as directory:
                fixture = bot_tests.BotReadingTests()
                fixture.extra_environment = {'READING_ENGINE': 'v8',
                    'PAYMENTS_DB_PATH': str(Path(directory)/'unused.sqlite3')}
                if value is not None:
                    fixture.extra_environment['PAYMENTS_ENABLED'] = value
                fixture.setUp()
                try:
                    self.assertFalse(fixture.bot.payments_service.requested)
                    self.assertEqual(len(fixture.bot.main_menu.keyboard), 3)
                    message = await fixture.run_mode('question')
                    self.assertIn(VALID_INITIATIVE_TEXT, message.answer.call_args.args[0])
                    fixture.model.assert_called_once()
                    self.assertFalse(Path(fixture.bot.payments_service.path).exists())
                    self.assertFalse(fixture.bot.paid_readings.tasks)
                finally:
                    await fixture.bot.bot.session.close()
                    fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()
