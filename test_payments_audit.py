"""Restart boundaries, rejected-update audit and offline recovery diagnostics."""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

import aiosqlite
from payments_service import PaymentsService, PaymentError, PACKAGES
from payments_readings import PaidReadings
from reading_service_v8 import ReadingServiceV8
import test_bot_reading_integration as bot_tests
from test_reading_engine_v8 import INITIATIVE_CARDS, VALID_INITIATIVE_TEXT


SECRET = 'offline-audit-signing-secret'


class RestartLedgerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name)/'ledger.sqlite3')
        self.service = self.reopen()

    def reopen(self, requested=True, secret=SECRET):
        return PaymentsService(self.path, secret, requested=requested)

    async def row(self, table, where='', args=()):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM '+table+' '+where, args) as cursor:
                return await cursor.fetchone()

    async def test_restart_at_every_invoice_stage_and_switch_off(self):
        invoice = await self.service.issue_invoice(1, 'moon_5')
        self.service = self.reopen(False)
        await self.service.validate_checkout(1, invoice['payload'], 'XTR', 200, 'query')
        self.service = self.reopen(False)
        self.assertTrue(await self.service.credit_purchase(1, invoice['payload'], 'XTR', 200, 'charge'))
        self.service = self.reopen(False)
        self.assertFalse(await self.service.credit_purchase(1, invoice['payload'], 'XTR', 200, 'charge'))
        self.assertEqual((await self.service.balance(1)).paid, 5)
        with self.assertRaises(PaymentError):
            await self.service.issue_invoice(1, 'moon_1')

    async def test_known_invoice_can_settle_when_signing_secret_is_missing(self):
        invoice = await self.service.issue_invoice(1, 'moon_1')
        self.service = self.reopen(True, secret='')
        await self.service.validate_checkout(1, invoice['payload'], 'XTR', 50, 'query')
        with self.assertRaises(PaymentError):
            await self.service.issue_invoice(1, 'moon_1')
        self.service = self.reopen(False, secret='')
        self.assertTrue(await self.service.credit_purchase(1, invoice['payload'], 'XTR', 50, 'charge'))
        with self.assertRaises(PaymentError):
            await self.service.credit_purchase(2, invoice['payload'], 'XTR', 50, 'wrong-owner')
        self.assertEqual((await self.service.balance(1)).paid, 1)

    async def test_expiry_cancelled_and_paid_invoices_cannot_start_new_checkout(self):
        expired = await self.service.issue_invoice(1, 'moon_1')
        invoice_row = await self.row('invoices')
        with patch('payments_service.time.time', return_value=invoice_row['expires_at']):
            for _ in range(2):
                with self.assertRaises(PaymentError):
                    await self.reopen().validate_checkout(1, expired['payload'], 'XTR', 50, 'expired')
            with self.assertRaises(PaymentError):
                await self.reopen().credit_purchase(1, expired['payload'], 'XTR', 50, 'expired-charge')
        self.assertEqual((await self.row('invoices'))['lifecycle'], 'expired')
        cancelled = await self.service.issue_invoice(1, 'moon_1')
        self.assertTrue(await self.service.cancel_invoice(cancelled['payload'], 1))
        with self.assertRaises(PaymentError):
            await self.reopen().validate_checkout(1, cancelled['payload'], 'XTR', 50, 'cancelled')
        with self.assertRaises(PaymentError):
            await self.reopen().credit_purchase(1, cancelled['payload'], 'XTR', 50, 'cancelled-charge')
        paid = await self.service.issue_invoice(1, 'moon_1')
        await self.service.validate_checkout(1, paid['payload'], 'XTR', 50, 'paid')
        self.assertFalse(await self.service.cancel_invoice(paid['payload'], 1))
        await self.service.credit_purchase(1, paid['payload'], 'XTR', 50, 'paid-charge')
        with self.assertRaises(PaymentError):
            await self.reopen().validate_checkout(1, paid['payload'], 'XTR', 50, 'paid')

    async def test_late_service_payment_from_approved_checkout_is_not_lost(self):
        invoice = await self.service.issue_invoice(1, 'moon_1')
        await self.service.validate_checkout(1, invoice['payload'], 'XTR', 50, 'query')
        row = await self.row('invoices')
        with patch('payments_service.time.time', return_value=row['expires_at']+100):
            with self.assertRaises(PaymentError):
                await self.reopen().validate_checkout(1, invoice['payload'], 'XTR', 50, 'different-query')
            self.assertTrue(await self.reopen(False).credit_purchase(1, invoice['payload'], 'XTR', 50, 'charge'))
        self.assertEqual((await self.service.balance(1)).paid, 1)

    async def test_duplicate_checkouts_one_query_id_and_no_new_checkout_session(self):
        invoice = await self.service.issue_invoice(1, 'moon_1')
        values = await asyncio.gather(*(self.reopen(False).validate_checkout(
            1, invoice['payload'], 'XTR', 50, 'same-query') for _ in range(8)))
        self.assertEqual(values, ['moon_1']*8)
        with self.assertRaises(PaymentError):
            await self.reopen(False).validate_checkout(1, invoice['payload'], 'XTR', 50, 'new-query')
        self.assertEqual((await self.service.balance(1)).paid, 0)

    async def test_same_checkout_query_cannot_be_rebound_to_other_payload(self):
        first = await self.service.issue_invoice(1,'moon_1')
        second = await self.service.issue_invoice(1,'moon_1')
        results = await asyncio.gather(*(self.reopen().validate_checkout(
            1, invoice['payload'],'XTR',50,'same-query') for invoice in (first,second)),
            return_exceptions=True)
        self.assertEqual(sum(isinstance(r,PaymentError) for r in results),1)
        self.assertEqual((await self.service.diagnostics())['audit_events'],1)

    async def test_conflicting_duplicate_updates_are_persistently_audited(self):
        first = await self.service.issue_invoice(1, 'moon_1')
        second = await self.service.issue_invoice(1, 'moon_1')
        await self.service.credit_purchase(1, first['payload'], 'XTR', 50, 'charge')
        for payload, charge in ((second['payload'], 'charge'), (first['payload'], 'other-charge')):
            with self.assertRaises(PaymentError):
                await self.reopen().credit_purchase(1, payload, 'XTR', 50, charge)
        self.assertEqual((await self.service.balance(1)).paid, 1)
        self.assertEqual((await self.service.diagnostics())['audit_events'], 2)
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT code,reference FROM payment_audit') as cursor:
                records = await cursor.fetchall()
        self.assertEqual({r[0] for r in records}, {'charge_conflict','invoice_conflict'})
        self.assertNotIn(first['payload'], repr(records))
        self.assertNotIn('charge', repr([r[1] for r in records]))

    async def test_nonce_is_globally_unique_and_signature_uses_compare_digest(self):
        with patch('payments_service.secrets.token_urlsafe', return_value='x'*22):
            invoice = await self.service.issue_invoice(1, 'moon_1')
            with self.assertRaises(PaymentError):
                await self.service.issue_invoice(2, 'moon_5')
        import hmac
        with patch('payments_service.hmac.compare_digest', wraps=hmac.compare_digest) as compare:
            await self.service.validate_checkout(1, invoice['payload'], 'XTR', 50)
            compare.assert_called_once()
        for payload in (invoice['payload'][:-1]+'Z', 'x'*129, ''):
            with self.assertRaises(PaymentError):
                await self.service.validate_checkout(1, payload, 'XTR', 50)

    async def test_full_long_charge_id_survives_restart(self):
        invoice = await self.service.issue_invoice(1, 'moon_1')
        charge = 'offline-charge-'+'x'*1000
        await self.service.credit_purchase(1, invoice['payload'], 'XTR', 50, charge)
        self.service = self.reopen()
        row = await self.row('purchases')
        self.assertEqual(row['telegram_payment_charge_id'], charge)
        self.assertFalse(await self.service.credit_purchase(1, invoice['payload'], 'XTR', 50, charge))

    async def test_completed_released_terminals_and_nonnegative_balances(self):
        await self.service.reserve((1,1),1)
        await self.service.finish((1,1), success=True, result={'text':'fixture'})
        self.assertEqual(await self.reopen().finish((1,1),success=False),'completed')
        await self.service.reserve((1,2),1)
        await self.service.finish((1,2),success=False)
        self.assertEqual(await self.reopen().finish((1,2),success=True,result={}), 'released')
        for column in ('free_remaining','paid_credits','debt'):
            with self.assertRaises(PaymentError):
                async with self.service.transaction() as db:
                    await db.execute(f'UPDATE users SET {column}=-1 WHERE user_id=1')
        balance = await self.service.balance(1)
        self.assertEqual((balance.free,balance.paid,balance.total),(2,0,2))

    async def test_ledger_path_is_resolved_once_against_working_directory(self):
        previous = os.getcwd()
        try:
            os.chdir(self.directory.name)
            service = PaymentsService('relative.sqlite3', SECRET, requested=True)
        finally:
            os.chdir(previous)
        await service.initialize()
        self.assertEqual(service.path, str(Path(self.directory.name)/'relative.sqlite3'))
        self.assertEqual((await service.balance(1)).free, 3)

    async def test_env_ledger_and_backup_patterns_are_ignored(self):
        import fnmatch
        patterns = Path('.gitignore').read_text().splitlines()
        for name in ('.env','.env.bak','payments.sqlite3','payments.sqlite3-wal',
                     'payments.sqlite3-shm','payments.sqlite3.backup','payments.backup',
                     'payments-2026.bak'):
            self.assertTrue(any(fnmatch.fnmatch(name,p) for p in patterns if p and not p.startswith('#')),name)

    async def test_unstatable_database_path_does_not_break_free_navigation(self):
        with patch('payments_service.Path.is_file', side_effect=PermissionError('offline')):
            self.assertFalse(self.service.exists)

    async def test_additive_migration_preserves_old_invoice_and_free_balance(self):
        # Schema before the audit: two invoice states, no expiry/checkout fields.
        async with aiosqlite.connect(self.path) as db:
            await db.execute("CREATE TABLE invoices(payload TEXT PRIMARY KEY,user_id INTEGER,package TEXT,status TEXT DEFAULT 'issued',created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            nonce = 'a'*22
            payload = f'mm1.{nonce}.{self.service._signature(1,"moon_1",nonce)}'
            await db.execute("INSERT INTO invoices(payload,user_id,package) VALUES (?,1,'moon_1')", (payload,))
            await db.commit()
        await self.service.initialize()
        await self.service.reserve((1,1),1)
        self.service = self.reopen(False)
        await self.service.initialize()
        await self.service.validate_checkout(1,payload,'XTR',50,'query')
        self.assertEqual((await self.service.balance(1)).free,2)
        expires = (await self.row('invoices'))['expires_at']
        await self.reopen().initialize()
        self.assertEqual((await self.row('invoices'))['expires_at'], expires)


class HandlerAuditTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture = bot_tests.BotReadingTests()
        self.fixture.extra_environment = {'PAYMENTS_ENABLED':'true','READING_ENGINE':'v8',
            'PAYMENT_PAYLOAD_SECRET':SECRET,'PAYMENTS_DB_PATH':str(Path(self.directory.name)/'ledger.sqlite3'),
            'ADMIN_IDS':'77'}
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bot,self.service,self.model = self.fixture.bot,self.fixture.bot.payments_service,self.fixture.model

    async def asyncTearDown(self):
        await self.bot.bot.session.close()

    def restart(self, *, requested=True, secret=SECRET):
        self.service = PaymentsService(self.service.path,secret,requested=requested)
        self.bot.payments_service = self.service
        self.bot.reading_service_v8 = ReadingServiceV8()
        self.bot.paid_readings = PaidReadings(self.service,self.bot.reading_service_v8,self.bot.draw_cards)
        self.bot.user_mode.clear()

    async def test_restarted_reserved_message_never_redraws_or_generates(self):
        await self.service.reserve((100,20),77)
        self.restart()
        message = self.fixture.message()
        await self.bot.handle_buttons(message)
        self.assertIn('уже обрабатывается', message.answer.call_args.args[0])
        self.model.assert_not_called()
        self.bot.draw_cards.assert_not_called()
        self.assertEqual((await self.service.balance(77)).free,2)

    async def test_restarted_completed_result_restores_without_user_mode_even_flag_off(self):
        self.bot.user_mode[77] = 'question'
        message = self.fixture.message()
        message.answer.side_effect = [None,RuntimeError('offline delivery')]
        with self.assertRaises(RuntimeError):
            await self.bot.handle_buttons(message)
        saved = await self.service.get_reservation((100,20),77)
        self.assertEqual(saved['status'],'completed')
        self.restart(requested=False,secret='')
        message.answer.side_effect = None
        await self.bot.handle_buttons(message)
        restored = self.bot.reading_service_v8.get((100,20))
        self.assertEqual((await restored.result())['text'],VALID_INITIATIVE_TEXT)
        self.assertEqual(restored.cards, INITIATIVE_CARDS)
        self.assertTrue(restored.delivered)
        self.model.assert_called_once()
        self.bot.draw_cards.assert_called_once()
        self.bot.save_history.assert_called_once()
        self.assertEqual((await self.service.balance(77)).free,2)

    async def test_restart_after_released_operation_never_regenerates(self):
        self.model.return_value = '{'
        await self.fixture.run_mode('question')
        self.restart()
        message = self.fixture.message()
        await self.bot.handle_buttons(message)
        self.assertEqual(message.answer.call_args.args[0],self.bot.FAILURE_MESSAGE)
        self.model.assert_called_once()
        self.bot.draw_cards.assert_called_once()
        self.assertEqual((await self.service.balance(77)).free,3)

    async def test_exact_reserve_generate_commit_delivery_order_without_message_dependency(self):
        events = []
        real_reserve,real_finish = self.service.reserve,self.service.finish
        async def reserve(*args,**kwargs):
            result = await real_reserve(*args,**kwargs)
            events.append('reserve_committed')
            return result
        def draw(count):
            with sqlite3.connect(self.service.path) as db:
                self.assertEqual(db.execute('SELECT status FROM reading_reservations').fetchone()[0],'reserved')
            events.append('draw')
            return INITIATIVE_CARDS
        def model(prompt):
            events.append('model')
            return {'payload':{'final_text':VALID_INITIATIVE_TEXT}}
        async def finish(*args,**kwargs):
            result = await real_finish(*args,**kwargs)
            with sqlite3.connect(self.service.path) as db:
                state,raw = db.execute('SELECT status,result_json FROM reading_reservations').fetchone()
            self.assertEqual(state,'completed')
            self.assertEqual(json.loads(raw)['cards'],INITIATIVE_CARDS)
            events.append('result_and_completed_committed')
            return result
        self.bot.draw_cards.side_effect = draw
        self.model.side_effect = model
        message = self.fixture.message()
        async def answer(*args,**kwargs):
            self.assertIn('result_and_completed_committed',events)
            events.append('telegram')
        message.answer.side_effect = answer
        self.bot.user_mode[77] = 'question'
        with patch.object(self.service,'reserve',side_effect=reserve), patch.object(self.service,'finish',side_effect=finish):
            await self.bot.handle_buttons(message)
        self.assertEqual(events[:4],['reserve_committed','draw','model','result_and_completed_committed'])
        self.assertTrue(all(e=='telegram' for e in events[4:]))

    async def test_diagnostics_admin_only_safe_and_does_not_change_business_rows(self):
        await self.service.reserve((100,20),77)
        invoice = await self.service.issue_invoice(77,'moon_1')
        await self.service.credit_purchase(77,invoice['payload'],'XTR',50,'private-charge-id')
        await self.service.claim_refund('private-charge-id')
        before = await self.service.get_reservation((100,20),77)
        message = self.fixture.message('/paymentdiag')
        message.from_user.id = 99
        await self.bot.handle_buttons(message)
        self.assertEqual(message.answer.call_args.args[0],'Команда недоступна.')
        message.from_user.id = 77
        self.service.requested = False
        await self.bot.handle_buttons(message)
        text = message.answer.call_args.args[0]
        self.assertIn('reserved: 1',text)
        self.assertIn('refund_pending: 1',text)
        self.assertNotIn('private-charge-id',text)
        self.assertNotIn(invoice['payload'],text)
        self.assertNotIn(SECRET,text)
        self.assertEqual(before,await self.service.get_reservation((100,20),77))
        purchase,claimed = await self.service.claim_refund('private-charge-id')
        self.assertFalse(claimed)
        self.assertEqual(purchase['status'],'refund_pending')

    async def test_concurrent_refunds_and_failed_local_commit_never_repeat_bot_api(self):
        invoice = await self.service.issue_invoice(77,'moon_5')
        await self.service.credit_purchase(77,invoice['payload'],'XTR',200,'private-charge')
        message1,message2 = self.fixture.message(),self.fixture.message()
        confirmed, failed = False, False
        real_commit = aiosqlite.Connection.commit
        async def external_refund(**kwargs):
            nonlocal confirmed
            confirmed = True
            return True
        async def commit(connection):
            nonlocal failed
            if confirmed and not failed:
                async with connection.execute("SELECT status FROM purchases WHERE telegram_payment_charge_id='private-charge'") as cursor:
                    row = await cursor.fetchone()
                if row and row[0] == 'refunded':
                    failed = True
                    raise aiosqlite.OperationalError('offline simulated commit failure')
            await real_commit(connection)
        with patch.object(self.bot.bot,'refund_star_payment',new_callable=AsyncMock,side_effect=external_refund) as refund, \
             patch.object(aiosqlite.Connection,'commit',commit):
            await asyncio.gather(self.bot.refund_purchase(message1,'private-charge'),
                                 self.bot.refund_purchase(message2,'private-charge'))
            await self.bot.refund_purchase(message1,'private-charge')
            refund.assert_awaited_once()
        self.assertEqual((await self.service.claim_refund('private-charge'))[0]['status'],'refund_pending')
        self.restart()
        self.assertTrue(await self.service.complete_refund('private-charge'))
        self.assertFalse(await self.service.complete_refund('private-charge'))
        self.assertEqual((await self.service.balance(77)).paid,0)

    async def test_missing_secret_keeps_start_free_modes_and_known_payment_working(self):
        invoice = await self.service.issue_invoice(77,'moon_1')
        self.restart(secret='')
        message = self.fixture.message()
        await self.bot.start_command(message)
        self.assertIn('Добро пожаловать',message.answer.call_args.args[0])
        await self.fixture.test_day_full_and_chat_keep_legacy_path_under_v8()
        message.successful_payment = types.SimpleNamespace(invoice_payload=invoice['payload'],
            currency='XTR',total_amount=50,telegram_payment_charge_id='late-charge')
        await self.bot.successful_payment(message)
        self.assertEqual((await self.service.balance(77)).paid,1)
        await self.fixture.run_mode('question',message_id=100)
        self.model.assert_not_called()

    async def test_checkout_duplicate_answers_and_success_receipt_after_commit(self):
        invoice = await self.service.issue_invoice(77,'moon_1')
        self.restart(requested=False,secret='')
        def query():
            return types.SimpleNamespace(id='query',from_user=types.SimpleNamespace(id=77),
                invoice_payload=invoice['payload'],currency='XTR',total_amount=50,answer=AsyncMock())
        first,second = query(),query()
        await asyncio.gather(self.bot.checkout_payment(first), self.bot.checkout_payment(second))
        first.answer.assert_awaited_once();second.answer.assert_awaited_once()
        self.assertTrue(first.answer.call_args.kwargs['ok'])
        self.assertTrue(second.answer.call_args.kwargs['ok'])
        message = self.fixture.message()
        message.successful_payment = types.SimpleNamespace(invoice_payload=invoice['payload'],
            currency='XTR',total_amount=50,telegram_payment_charge_id='private-charge')
        async def send(text,**kwargs):
            reopened = PaymentsService(self.service.path,'',requested=False)
            self.assertEqual((await reopened.balance(77)).paid,1)
        message.answer.side_effect = send
        await self.bot.successful_payment(message)
        self.restart(requested=False,secret='')
        await self.bot.successful_payment(message)
        self.assertIn('уже учтена',message.answer.call_args.args[0])

    async def test_telegram_receipt_failure_after_commit_does_not_recredit(self):
        invoice = await self.service.issue_invoice(77,'moon_1')
        message = self.fixture.message()
        message.successful_payment = types.SimpleNamespace(invoice_payload=invoice['payload'],
            currency='XTR',total_amount=50,telegram_payment_charge_id='private-charge')
        message.answer.side_effect = RuntimeError('offline receipt failure')
        with self.assertRaises(RuntimeError): await self.bot.successful_payment(message)
        self.restart(requested=False)
        message.answer.side_effect = None
        await self.bot.successful_payment(message)
        self.assertEqual((await self.service.balance(77)).paid,1)
        self.assertIn('уже учтена',message.answer.call_args.args[0])

    async def test_concurrent_successful_payment_handlers_credit_once(self):
        invoice = await self.service.issue_invoice(77,'moon_5')
        messages = [self.fixture.message() for _ in range(2)]
        for message in messages:
            message.successful_payment = types.SimpleNamespace(invoice_payload=invoice['payload'],
                currency='XTR',total_amount=200,telegram_payment_charge_id='private-charge')
        await asyncio.gather(*(self.bot.successful_payment(m) for m in messages))
        self.assertEqual((await self.service.balance(77)).paid,5)
        replies = [m.answer.call_args.args[0] for m in messages]
        self.assertEqual(sum('Эта покупка уже учтена.' in r for r in replies),1)

    async def test_purchase_commit_failure_never_sends_success_or_grants_credit(self):
        invoice = await self.service.issue_invoice(77,'moon_1')
        message = self.fixture.message()
        message.successful_payment = types.SimpleNamespace(invoice_payload=invoice['payload'],
            currency='XTR',total_amount=50,telegram_payment_charge_id='private-charge')
        real_commit = aiosqlite.Connection.commit
        async def commit(connection):
            async with connection.execute('SELECT COUNT(*) FROM purchases') as cursor:
                row = await cursor.fetchone()
            if row[0]:
                raise aiosqlite.OperationalError('offline commit failure')
            await real_commit(connection)
        with patch.object(aiosqlite.Connection,'commit',commit):
            await self.bot.successful_payment(message)
        self.assertIn('Не удалось подтвердить',message.answer.call_args.args[0])
        self.assertEqual((await self.service.balance(77)).paid,0)
        await self.bot.successful_payment(message)
        self.assertEqual((await self.service.balance(77)).paid,1)

    async def test_last_free_notice_is_committed_once_without_changing_model_text(self):
        for index in range(3):
            message = await self.fixture.run_mode('question',message_id=index)
        notice = 'Это был последний бесплатный расклад. Продолжить можно после покупки пакета за Stars.'
        self.assertTrue(message.answer.call_args.args[0].endswith(notice))
        self.assertIn(VALID_INITIATIVE_TEXT,message.answer.call_args.args[0])
        saved = await self.service.get_reservation((100,2),77)
        self.assertEqual(json.loads(saved['result_json'])['credit_notice'],notice)
        self.assertEqual(json.loads(saved['result_json'])['text'],VALID_INITIATIVE_TEXT)
        count = message.answer.await_count
        await self.bot.handle_buttons(message)
        self.assertEqual(message.answer.await_count,count)
        self.assertEqual(self.model.call_count,3)

    async def test_precheckout_real_deadline_rejects_hung_validation(self):
        query = types.SimpleNamespace(id='query',from_user=types.SimpleNamespace(id=77),
            invoice_payload='offline',currency='XTR',total_amount=50,answer=AsyncMock())
        async def hung(*args):
            await asyncio.Event().wait()
        started = asyncio.get_running_loop().time()
        with patch.object(self.service,'validate_checkout',side_effect=hung):
            await self.bot.checkout_payment(query)
        elapsed = asyncio.get_running_loop().time()-started
        self.assertLess(elapsed,5)
        query.answer.assert_awaited_once()
        self.assertFalse(query.answer.call_args.kwargs['ok'])


if __name__ == '__main__':
    unittest.main()
