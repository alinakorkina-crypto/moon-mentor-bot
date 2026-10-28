"""SQLite concurrency and payment validation with artificial, local data."""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aiosqlite
from payments_service import PaymentsService, PaymentError, PACKAGES


class PaymentLedgerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / 'payments.sqlite3')
        self.service = PaymentsService(self.path, 'offline-payload-signing-secret', requested=True)

    async def buy(self, user_id=1, package='moon_1', charge='offline-charge'):
        invoice = await self.service.issue_invoice(user_id, package)
        await self.service.credit_purchase(user_id, invoice['payload'], 'XTR', invoice['stars'], charge)
        return invoice

    async def test_flag_default_and_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(PaymentsService.from_env().requested)
        with patch.dict(os.environ, {'PAYMENTS_ENABLED': 'false'}, clear=True):
            self.assertFalse(PaymentsService.from_env().requested)
        with patch.dict(os.environ, {'PAYMENTS_ENABLED': 'true'}, clear=True):
            service = PaymentsService.from_env()
            self.assertTrue(service.requested)
            self.assertFalse(service.ready)
        self.assertFalse(Path('payments.sqlite3').exists())

    async def test_new_and_existing_user_only_receive_three_free_once(self):
        await self.service.initialize()
        for _ in range(3):
            balance = await self.service.balance(1)
            self.assertEqual((balance.free, balance.paid, balance.total), (3, 0, 3))
            await self.service.initialize()
        service2 = PaymentsService(self.path, 'offline-payload-signing-secret', requested=True)
        self.assertEqual((await service2.balance(1)).free, 3)

    async def test_reservation_uses_free_first_then_paid(self):
        await self.buy(package='moon_5')
        for index in range(4):
            row, new = await self.service.reserve((100, index), 1)
            self.assertTrue(new)
            self.assertEqual(row['source'], 'free' if index < 3 else 'paid')
            await self.service.finish((100, index), success=True, result={'text': 'local fixture'})
        balance = await self.service.balance(1)
        self.assertEqual((balance.free, balance.paid), (0, 4))
        stats = await self.service.statistics()
        self.assertEqual((stats['free'], stats['paid']), (3, 1))

    async def test_release_idempotent_returns_same_source(self):
        await self.buy()
        for index in range(3):
            await self.service.reserve((1, index), 1)
            await self.service.finish((1, index), success=True, result={})
        row, _ = await self.service.reserve((1, 4), 1)
        self.assertEqual(row['source'], 'paid')
        await asyncio.gather(*(self.service.finish((1, 4), success=False) for _ in range(6)))
        self.assertEqual((await self.service.balance(1)).paid, 1)
        self.assertEqual(await self.service.finish((1, 4), success=True, result={}), 'released')

    async def test_concurrent_requests_cannot_overspend(self):
        await self.service.initialize()
        services = [PaymentsService(self.path, 'offline-payload-signing-secret', requested=True) for _ in range(12)]
        rows = await asyncio.gather(*(s.reserve((100, index), 1) for index, s in enumerate(services)))
        self.assertEqual(sum(new for _, new in rows), 3)
        self.assertEqual(sum(row is None for row, _ in rows), 9)
        self.assertEqual((await self.service.balance(1)).free, 0)

    async def test_concurrent_duplicate_only_one_reservation(self):
        await self.service.initialize()
        rows = await asyncio.gather(*(self.service.reserve((100, 1), 1) for _ in range(10)))
        self.assertEqual(sum(new for _, new in rows), 1)
        self.assertEqual((await self.service.balance(1)).free, 2)
        with self.assertRaises(PaymentError):
            await self.service.reserve((100, 1), 2)

    async def test_invoice_validation_all_packages_and_invalid_values(self):
        for package, (stars, credits) in PACKAGES.items():
            invoice = await self.service.issue_invoice(1, package)
            self.assertLessEqual(len(invoice['payload'].encode()), 128)
            self.assertEqual((invoice['stars'], invoice['credits']), (stars, credits))
            self.assertEqual(await self.service.validate_checkout(1, invoice['payload'], 'XTR', stars), package)
            for user, payload, currency, amount in (
                (2, invoice['payload'], 'XTR', stars),
                (1, invoice['payload'], 'USD', stars),
                (1, invoice['payload'], 'XTR', stars+1),
                (1, 'invalid', 'XTR', stars),
                (1, 'x'*129, 'XTR', stars),
                (1, invoice['payload'][:-1] + ('a' if invoice['payload'][-1] != 'a' else 'b'), 'XTR', stars),
            ):
                with self.subTest(package=package, invalid=currency):
                    with self.assertRaises(PaymentError):
                        await self.service.validate_checkout(user, payload, currency, amount)

    async def test_stored_payload_must_still_have_correct_signature(self):
        invoice = await self.service.issue_invoice(1, 'moon_1')
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE invoices SET package='moon_10' WHERE payload=?", (invoice['payload'],))
            await db.commit()
        with self.assertRaises(PaymentError):
            await self.service.validate_checkout(1, invoice['payload'], 'XTR', 350)

    async def test_purchase_duplicates_and_same_invoice_replay(self):
        invoice = await self.buy(package='moon_10')
        results = await asyncio.gather(*(self.service.credit_purchase(1, invoice['payload'], 'XTR', 350, 'offline-charge') for _ in range(8)))
        self.assertFalse(any(results))
        self.assertEqual((await self.service.balance(1)).paid, 10)
        with self.assertRaises(PaymentError):
            await self.service.credit_purchase(1, invoice['payload'], 'XTR', 350, 'different-charge')
        with self.assertRaises(PaymentError):
            await self.service.validate_checkout(1, invoice['payload'], 'XTR', 350)

    async def test_concurrent_successful_payment_and_refund_claims(self):
        invoice = await self.service.issue_invoice(1, 'moon_5')
        results = await asyncio.gather(*(self.service.credit_purchase(
            1, invoice['payload'], 'XTR', 200, 'offline-concurrent-charge') for _ in range(10)))
        self.assertEqual(sum(results), 1)
        self.assertEqual((await self.service.balance(1)).paid, 5)
        claims = await asyncio.gather(*(self.service.claim_refund('offline-concurrent-charge') for _ in range(8)))
        self.assertEqual(sum(claimed for _, claimed in claims), 1)
        await asyncio.gather(*(self.service.complete_refund('offline-concurrent-charge') for _ in range(5)))
        self.assertEqual((await self.service.balance(1)).paid, 0)
        self.assertEqual((await self.service.statistics())['refunds'], 1)

    async def test_refund_once_with_spent_credit_debt_and_future_purchase(self):
        await self.buy(package='moon_5')
        for index in range(5):
            await self.service.reserve((1, index), 1)
            await self.service.finish((1, index), success=True, result={})
        purchase, claimed = await self.service.claim_refund('offline-charge')
        self.assertTrue(claimed)
        self.assertEqual(purchase['credits'], 5)
        self.assertFalse((await self.service.claim_refund('offline-charge'))[1])
        self.assertTrue(await self.service.complete_refund('offline-charge'))
        self.assertFalse(await self.service.complete_refund('offline-charge'))
        balance = await self.service.balance(1)
        self.assertEqual((balance.paid, balance.debt), (0, 2))
        await self.buy(package='moon_5', charge='second-charge')
        balance = await self.service.balance(1)
        self.assertEqual((balance.paid, balance.debt), (3, 0))

    async def test_refunded_reserved_paid_credit_release_settles_debt(self):
        await self.buy()
        for index in range(3):
            await self.service.reserve((1, index), 1)
            await self.service.finish((1, index), success=True, result={})
        await self.service.reserve((1, 3), 1)
        await self.service.claim_refund('offline-charge')
        await self.service.complete_refund('offline-charge')
        self.assertEqual((await self.service.balance(1)).debt, 1)
        await self.service.finish((1, 3), success=False)
        balance = await self.service.balance(1)
        self.assertEqual((balance.paid, balance.debt), (0, 0))

    async def test_refunded_purchase_delivery_cannot_recredit(self):
        invoice = await self.buy()
        await self.service.claim_refund('offline-charge')
        await self.service.complete_refund('offline-charge')
        self.assertFalse(await self.service.credit_purchase(1, invoice['payload'], 'XTR', 50, 'offline-charge'))
        self.assertEqual((await self.service.balance(1)).paid, 0)

    async def test_sqlite_files_ignored_by_repository(self):
        # Check ignore rules locally without spawning git from an offline test.
        patterns = Path('.gitignore').read_text().splitlines()
        import fnmatch
        for name in ('payments.sqlite3','payments.sqlite3-wal','payments.sqlite3-shm',
                     'payments.sqlite3-journal','payments.db','payments.db-wal','etilqs_offline'):
            self.assertTrue(any(fnmatch.fnmatch(name,p) for p in patterns if p and not p.startswith('#')), name)


if __name__ == '__main__':
    unittest.main()
