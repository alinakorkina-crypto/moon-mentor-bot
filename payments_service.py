"""Transactional Stars credit ledger. This module never calls Telegram or AI."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

import aiosqlite


PACKAGES = {
    "moon_1": (50, 1),
    "moon_5": (200, 5),
    "moon_10": (350, 10),
}
INVOICE_TTL_SECONDS = 900
UNAVAILABLE = "Сейчас покупка и платные расклады недоступны. Попробуйте немного позже."


class PaymentError(Exception):
    """Safe public classification; never includes payloads or credentials."""
    def __init__(self, message, code="validation_failed"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Balance:
    free: int
    paid: int
    debt: int = 0

    @property
    def total(self):
        return self.free + self.paid


class PaymentsService:
    def __init__(self, path: str, secret: str = "", *, requested: bool = False):
        self.path = os.path.abspath(os.path.expanduser(path)) if path not in ("", ":memory:") else path
        self._secret = secret.encode()
        self.requested = requested

    @classmethod
    def from_env(cls):
        return cls(os.getenv("PAYMENTS_DB_PATH", "payments.sqlite3"),
                   os.getenv("PAYMENT_PAYLOAD_SECRET", "").strip(),
                   requested=os.getenv("PAYMENTS_ENABLED", "false").strip().lower() == "true")

    @property
    def ready(self):
        return bool(self._secret and not re.fullmatch(rb"__SECRET[\s\S]*__", self._secret)
                    and self.path and self.path != ":memory:")

    @property
    def exists(self):
        try:
            return bool(self.path and Path(self.path).is_file())
        except OSError:
            return False

    @staticmethod
    def reference(kind, value):
        return kind + "-" + hashlib.sha256(str(value).encode()).hexdigest()[:16]

    @asynccontextmanager
    async def transaction(self):
        try:
            async with aiosqlite.connect(self.path, timeout=2) as db:
                db.row_factory = aiosqlite.Row
                await db.execute("PRAGMA busy_timeout=2000")
                await db.execute("PRAGMA foreign_keys=ON")
                await db.executescript("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        free_remaining INTEGER NOT NULL DEFAULT 3 CHECK(free_remaining >= 0),
                        paid_credits INTEGER NOT NULL DEFAULT 0 CHECK(paid_credits >= 0),
                        debt INTEGER NOT NULL DEFAULT 0 CHECK(debt >= 0),
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS invoices (
                        payload TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(user_id),
                        package TEXT NOT NULL CHECK(package IN ('moon_1','moon_5','moon_10')),
                        status TEXT NOT NULL DEFAULT 'issued' CHECK(status IN ('issued','paid')),
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS purchases (
                        telegram_payment_charge_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(user_id),
                        invoice_payload TEXT NOT NULL UNIQUE REFERENCES invoices(payload),
                        stars_amount INTEGER NOT NULL CHECK(stars_amount > 0),
                        credits INTEGER NOT NULL CHECK(credits > 0),
                        status TEXT NOT NULL DEFAULT 'paid'
                          CHECK(status IN ('paid', 'refund_pending', 'refunded')),
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        refunded_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS reading_reservations (
                        chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL REFERENCES users(user_id),
                        source TEXT NOT NULL CHECK(source IN ('free','paid')),
                        status TEXT NOT NULL CHECK(status IN ('reserved','completed','released')),
                        result_json TEXT, history_recorded INTEGER NOT NULL DEFAULT 0,
                        delivered INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY(chat_id, message_id)
                    );
                    CREATE TABLE IF NOT EXISTS payment_audit (
                        id INTEGER PRIMARY KEY, code TEXT NOT NULL,
                        reference TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                await db.execute("BEGIN IMMEDIATE")
                try:
                    # Additive migration preserves old issued/paid invoices and
                    # their original expiry across upgrades and process restarts.
                    async with db.execute("PRAGMA table_info(invoices)") as cursor:
                        columns = {row['name'] for row in await cursor.fetchall()}
                    additions = {
                        "lifecycle": "TEXT NOT NULL DEFAULT 'issued' CHECK(lifecycle IN ('issued','approved','paid','expired','cancelled'))",
                        "expires_at": "INTEGER", "checkout_at": "INTEGER",
                        "checkout_id": "TEXT", "nonce": "TEXT",
                    }
                    for name, declaration in additions.items():
                        if name not in columns:
                            await db.execute(f"ALTER TABLE invoices ADD COLUMN {name} {declaration}")
                    if "lifecycle" not in columns:
                        await db.execute("UPDATE invoices SET lifecycle=status")
                    await db.execute("UPDATE invoices SET expires_at=CAST(strftime('%s',created_at) AS INTEGER)+? WHERE expires_at IS NULL", (INVOICE_TTL_SECONDS,))
                    await db.execute("UPDATE invoices SET nonce=substr(payload,5,22) WHERE nonce IS NULL")
                    await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS invoices_nonce ON invoices(nonce)")
                    await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS invoices_checkout_id ON invoices(checkout_id) WHERE checkout_id IS NOT NULL")
                    await db.execute("PRAGMA user_version=2")
                    yield db
                    await db.commit()
                except BaseException:
                    await db.rollback()
                    raise
        except (aiosqlite.Error, OSError, ValueError):
            raise PaymentError("Учёт платежей временно недоступен") from None

    async def initialize(self):
        async with self.transaction():
            pass

    async def _user(self, db, user_id):
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))

    async def _one(self, db, sql, args=()):
        async with db.execute(sql, args) as cursor:
            return await cursor.fetchone()

    async def balance(self, user_id):
        async with self.transaction() as db:
            await self._user(db, user_id)
            row = await self._one(db, "SELECT * FROM users WHERE user_id=?", (user_id,))
            return Balance(row["free_remaining"], row["paid_credits"], row["debt"])

    async def get_reservation(self, key, user_id):
        async with self.transaction() as db:
            row = await self._one(db, "SELECT * FROM reading_reservations WHERE chat_id=? AND message_id=?", key)
            if row and row['user_id'] != user_id:
                raise PaymentError("Операция недоступна")
            return dict(row) if row else None

    async def reserve(self, key, user_id, *, allow_new=True):
        """Return (reservation, is_new). None means no available credit."""
        async with self.transaction() as db:
            row = await self._one(db, "SELECT * FROM reading_reservations WHERE chat_id=? AND message_id=?", key)
            if row:
                if row["user_id"] != user_id:
                    raise PaymentError("Операция недоступна")
                return dict(row), False
            if not allow_new:
                raise PaymentError("Новые расклады недоступны")
            await self._user(db, user_id)
            row = await self._one(db, "SELECT * FROM users WHERE user_id=?", (user_id,))
            source = "free" if row["free_remaining"] else "paid" if row["paid_credits"] else None
            if source is None:
                return None, False
            column = "free_remaining" if source == "free" else "paid_credits"
            await db.execute(f"UPDATE users SET {column}={column}-1, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (user_id,))
            await db.execute("INSERT INTO reading_reservations(chat_id,message_id,user_id,source,status) VALUES (?,?,?,?,'reserved')", (*key, user_id, source))
            row = await self._one(db, "SELECT * FROM reading_reservations WHERE chat_id=? AND message_id=?", key)
            return dict(row), True

    async def _add_paid(self, db, user_id, amount):
        row = await self._one(db, "SELECT debt FROM users WHERE user_id=?", (user_id,))
        settled = min(row["debt"], amount)
        await db.execute("UPDATE users SET debt=debt-?, paid_credits=paid_credits+?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (settled, amount-settled, user_id))

    async def finish(self, key, *, success: bool, result=None):
        async with self.transaction() as db:
            row = await self._one(db, "SELECT * FROM reading_reservations WHERE chat_id=? AND message_id=?", key)
            if row is None:
                raise PaymentError("Резервация не найдена")
            if row["status"] != "reserved":
                return row["status"]
            if not success:
                if row["source"] == "free":
                    await db.execute("UPDATE users SET free_remaining=free_remaining+1, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (row["user_id"],))
                else:
                    await self._add_paid(db, row["user_id"], 1)
            elif row['source'] == 'free' and isinstance(result, dict) and 'text' in result:
                used = await self._one(db, "SELECT COUNT(*) AS n FROM reading_reservations WHERE user_id=? AND source='free' AND status='completed'", (row['user_id'],))
                if used['n'] == 2:
                    balance = await self._one(db, "SELECT paid_credits FROM users WHERE user_id=?", (row['user_id'],))
                    result = dict(result)
                    result['credit_notice'] = ("Это был последний бесплатный расклад. Следующие будут использовать купленные кредиты."
                        if balance['paid_credits'] else "Это был последний бесплатный расклад. Продолжить можно после покупки пакета за Stars.")
            status = "completed" if success else "released"
            await db.execute("UPDATE reading_reservations SET status=?, result_json=?, updated_at=CURRENT_TIMESTAMP WHERE chat_id=? AND message_id=?", (status, json.dumps(result, ensure_ascii=False) if success else None, *key))
            return status

    async def mark_delivery(self, key, *, history=False):
        column = "history_recorded" if history else "delivered"
        async with self.transaction() as db:
            await db.execute(f"UPDATE reading_reservations SET {column}=1, updated_at=CURRENT_TIMESTAMP WHERE chat_id=? AND message_id=? AND status='completed'", key)

    def _signature(self, user_id, package, nonce):
        return hmac.new(self._secret, f"{user_id}:{package}:{nonce}".encode(), hashlib.sha256).hexdigest()[:32]

    async def issue_invoice(self, user_id, package):
        if not self.ready or not self.requested or package not in PACKAGES:
            raise PaymentError("Покупка недоступна")
        nonce = secrets.token_urlsafe(16)
        payload = f"mm1.{nonce}.{self._signature(user_id, package, nonce)}"
        async with self.transaction() as db:
            await self._user(db, user_id)
            await db.execute("INSERT INTO invoices(payload,user_id,package,nonce,expires_at) VALUES (?,?,?,?,?)", (payload, user_id, package, nonce, int(time.time())+INVOICE_TTL_SECONDS))
        stars, credits = PACKAGES[package]
        return {"payload": payload, "stars": stars, "credits": credits}

    async def _verify(self, db, user_id, payload, currency, amount, *, allow_paid=False):
        if not isinstance(payload, str) or not re.fullmatch(r"mm1\.[A-Za-z0-9_-]{22}\.[a-f0-9]{32}", payload):
            raise PaymentError("Платёж не прошёл проверку")
        row = await self._one(db, "SELECT * FROM invoices WHERE payload=?", (payload,))
        if row is None or row["user_id"] != user_id or row["package"] not in PACKAGES:
            raise PaymentError("Платёж не прошёл проверку")
        # Existing invoices remain verifiable if sales or their current signing
        # secret are disabled. The durable, exact opaque token is authoritative;
        # it was signed and bound to this owner/catalog entry when issued.
        signature = (self._signature(user_id, row["package"], payload.split('.')[1])
                     if self.ready else row['payload'].split('.')[2])
        if not hmac.compare_digest(signature, payload.split('.')[2]):
            raise PaymentError("Платёж не прошёл проверку")
        if currency != "XTR" or type(amount) is not int or amount != PACKAGES[row["package"]][0]:
            raise PaymentError("Платёж не прошёл проверку")
        if row['lifecycle'] == 'cancelled':
            raise PaymentError("Счёт отменён", "invoice_cancelled")
        expired = row['lifecycle'] == 'expired' or row['expires_at'] <= int(time.time())
        # A successful payment authorized before expiry must not be lost just
        # because Telegram delivered its service update later.
        authorized = row['checkout_at'] is not None and row['checkout_at'] < row['expires_at']
        if row['status'] != 'paid' and expired and not (allow_paid and authorized):
            await db.execute("UPDATE invoices SET lifecycle='expired' WHERE payload=?", (payload,))
            raise PaymentError("Срок счёта истёк", "invoice_expired")
        if not allow_paid and row["status"] != "issued":
            raise PaymentError("Счёт уже оплачен")
        return dict(row)

    async def _audit(self, db, error, value):
        await db.execute("INSERT INTO payment_audit(code,reference) VALUES (?,?)",
                         (error.code, self.reference('event', value)))

    async def validate_checkout(self, user_id, payload, currency, amount, query_id=None):
        error = None
        async with self.transaction() as db:
            try:
                row = await self._verify(db, user_id, payload, currency, amount)
                if query_id and row['checkout_id'] not in (None, query_id):
                    raise PaymentError("Счёт уже обрабатывается", "checkout_conflict")
                if query_id:
                    bound = await self._one(db, "SELECT payload FROM invoices WHERE checkout_id=?", (query_id,))
                    if bound and bound['payload'] != payload:
                        raise PaymentError("Проверка уже относится к другому счёту", "checkout_conflict")
                await db.execute("UPDATE invoices SET lifecycle='approved', checkout_at=COALESCE(checkout_at,?), checkout_id=COALESCE(checkout_id,?) WHERE payload=?",
                                 (int(time.time()), query_id, payload))
                package = row['package']
            except PaymentError as rejected:
                error = rejected
                await self._audit(db, error, payload)
        if error:
            raise error
        return package

    async def cancel_invoice(self, payload, user_id):
        async with self.transaction() as db:
            cursor = await db.execute("UPDATE invoices SET lifecycle='cancelled' WHERE payload=? AND user_id=? AND lifecycle='issued'", (payload, user_id))
            return cursor.rowcount == 1

    async def credit_purchase(self, user_id, payload, currency, amount, charge_id):
        if not isinstance(charge_id, str) or not charge_id.strip():
            raise PaymentError("Некорректный платёж")
        error = None
        credited = False
        async with self.transaction() as db:
            try:
                invoice = await self._verify(db, user_id, payload, currency, amount, allow_paid=True)
                existing = await self._one(db, "SELECT * FROM purchases WHERE telegram_payment_charge_id=?", (charge_id,))
                if existing:
                    if existing["user_id"] != user_id or existing["invoice_payload"] != payload:
                        raise PaymentError("Некорректный платёж", "charge_conflict")
                else:
                    if invoice["status"] != "issued":
                        raise PaymentError("Счёт уже оплачен", "invoice_conflict")
                    await self._user(db, user_id)
                    stars, credits = PACKAGES[invoice['package']]
                    await db.execute("INSERT INTO purchases(telegram_payment_charge_id,user_id,invoice_payload,stars_amount,credits) VALUES (?,?,?,?,?)", (charge_id, user_id, payload, stars, credits))
                    await db.execute("UPDATE invoices SET status='paid', lifecycle='paid' WHERE payload=?", (payload,))
                    await self._add_paid(db, user_id, credits)
                    credited = True
            except PaymentError as rejected:
                error = rejected
                await self._audit(db, error, charge_id)
        if error:
            raise error
        return credited

    async def claim_refund(self, charge_id):
        async with self.transaction() as db:
            row = await self._one(db, "SELECT * FROM purchases WHERE telegram_payment_charge_id=?", (charge_id,))
            if row is None:
                raise PaymentError("Покупка не найдена")
            if row["status"] != "paid":
                return dict(row), False
            await db.execute("UPDATE purchases SET status='refund_pending' WHERE telegram_payment_charge_id=?", (charge_id,))
            return dict(row), True

    async def complete_refund(self, charge_id):
        async with self.transaction() as db:
            row = await self._one(db, "SELECT * FROM purchases WHERE telegram_payment_charge_id=?", (charge_id,))
            if row is None or row["status"] != "refund_pending":
                return False
            balance = await self._one(db, "SELECT paid_credits FROM users WHERE user_id=?", (row["user_id"],))
            removed = min(balance["paid_credits"], row["credits"])
            await db.execute("UPDATE users SET paid_credits=paid_credits-?, debt=debt+?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (removed, row["credits"]-removed, row["user_id"]))
            await db.execute("UPDATE purchases SET status='refunded', refunded_at=CURRENT_TIMESTAMP WHERE telegram_payment_charge_id=?", (charge_id,))
            return True

    async def diagnostics(self):
        """Read-only business diagnostics; identifiers are nonreversible hashes."""
        async with self.transaction() as db:
            reserved = await self._one(db, "SELECT COUNT(*) AS n FROM reading_reservations WHERE status='reserved'")
            pending = await self._one(db, "SELECT COUNT(*) AS n FROM purchases WHERE status='refund_pending'")
            events = await self._one(db, "SELECT COUNT(*) AS n FROM payment_audit")
            async with db.execute("SELECT chat_id,message_id,created_at FROM reading_reservations WHERE status='reserved' ORDER BY created_at LIMIT 20") as cursor:
                readings = [(self.reference('reading', f"{r['chat_id']}:{r['message_id']}"), r['created_at']) for r in await cursor.fetchall()]
            async with db.execute("SELECT telegram_payment_charge_id,created_at FROM purchases WHERE status='refund_pending' ORDER BY created_at LIMIT 20") as cursor:
                refunds = [(self.reference('refund', r['telegram_payment_charge_id']), r['created_at']) for r in await cursor.fetchall()]
            return {"reserved": reserved['n'], "refund_pending": pending['n'],
                    "audit_events": events['n'], "readings": readings, "refunds": refunds}

    async def statistics(self):
        async with self.transaction() as db:
            purchases = await self._one(db, "SELECT COUNT(*) AS purchases, COALESCE(SUM(stars_amount),0) AS stars, COALESCE(SUM(credits),0) AS credits, COALESCE(SUM(status='refunded'),0) AS refunds FROM purchases")
            usage = await self._one(db, "SELECT COALESCE(SUM(source='free'),0) AS free, COALESCE(SUM(source='paid'),0) AS paid FROM reading_reservations WHERE status='completed'")
            users = await self._one(db, "SELECT COUNT(*) AS active FROM users WHERE free_remaining+paid_credits>0")
            return dict(purchases) | dict(usage) | dict(users)


def balance_text(balance):
    text = f"🌙 Ваш баланс\n\nБесплатные: {balance.free}\nКупленные: {balance.paid}\nВсего доступно: {balance.total}"
    if balance.debt:
        text += f"\nКорректировка после возврата: {balance.debt}. Она будет учтена при следующей покупке."
    return text
