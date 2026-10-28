"""Private payment tickets and durable at-most-once delivery claims. No network IO."""
import re
import secrets
import time

from payments_service import PaymentError

LIMIT = 1500
COOLDOWN = 300
PROMPT = ('Опишите проблему с оплатой одним сообщением.\n\n'
          'Не отправляйте данные банковской карты, пароли и коды подтверждения.')
SAFE_ERROR = 'Обращение недоступно или уже закрыто.'
UNAVAILABLE = 'Поддержка временно недоступна. Попробуйте немного позже.'
# Never persist recognizable credentials, invoice payloads or card numbers.
SENSITIVE = re.compile(r'sk-[\w-]+|Bearer\s+\S+|__SECRET.*?__|\b\d{6,}:[\w-]+|\bmm1\.[\w.-]+|(?<!\d)(?:\d[ -]?){13,19}(?!\d)|(?:password|пароль|cvv|cvc|код подтверждения)\s*[:=]\s*\S+', re.I)


def checked_text(text):
    text = text.strip()
    if not text or len(text) > LIMIT:
        raise PaymentError('Напишите одно сообщение длиной до 1500 символов.')
    if SENSITIVE.search(text):
        raise PaymentError('Удалите платёжные реквизиты, ключи и секретные данные из сообщения.')
    return text


class SupportService:
    def __init__(self, payments):
        self.payments = payments

    async def schema(self, db):
        statements = (
            """CREATE TABLE IF NOT EXISTS support_sessions (
              user_id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, created_at INTEGER NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS support_tickets (
              number TEXT PRIMARY KEY, user_id INTEGER NOT NULL, username TEXT NOT NULL,
              display_name TEXT NOT NULL, text TEXT NOT NULL CHECK(length(text)<=1500),
              status TEXT NOT NULL CHECK(status IN ('open','closed')),
              created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""",
            "CREATE UNIQUE INDEX IF NOT EXISTS support_one_open ON support_tickets(user_id) WHERE status='open'",
            """CREATE TABLE IF NOT EXISTS support_operations (
              chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, kind TEXT NOT NULL,
              ticket TEXT NOT NULL REFERENCES support_tickets(number),
              created_at INTEGER NOT NULL, PRIMARY KEY(chat_id,message_id))""",
            """CREATE TABLE IF NOT EXISTS support_messages (
              id INTEGER PRIMARY KEY, ticket TEXT NOT NULL REFERENCES support_tickets(number),
              recipient INTEGER NOT NULL, text TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('claimed','sent','uncertain')),
              created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""",
        )
        for sql in statements:
            await db.execute(sql)

    async def start(self, user_id, chat_id):
        async with self.payments.transaction() as db:
            await self.schema(db)
            row = await self.payments._one(db, "SELECT number FROM support_tickets WHERE user_id=? AND status='open'", (user_id,))
            if row:
                return f"У вас уже есть открытое обращение №{row['number']}. Дождитесь ответа поддержки."
            await db.execute('INSERT OR REPLACE INTO support_sessions VALUES (?,?,?)', (user_id, chat_id, int(time.time())))
        return PROMPT

    async def waiting(self, user_id, chat_id):
        if not self.payments.exists:
            return False
        async with self.payments.transaction() as db:
            await self.schema(db)
            return bool(await self.payments._one(db, 'SELECT 1 FROM support_sessions WHERE user_id=? AND chat_id=?', (user_id, chat_id)))

    async def cancel(self, user_id):
        async with self.payments.transaction() as db:
            await self.schema(db)
            await db.execute('DELETE FROM support_sessions WHERE user_id=?', (user_id,))

    async def _outgoing(self, db, ticket, recipient, text):
        now = int(time.time())
        cursor = await db.execute("INSERT INTO support_messages(ticket,recipient,text,status,created_at,updated_at) VALUES (?,?,?,'claimed',?,?)", (ticket, recipient, text, now, now))
        return (cursor.lastrowid, recipient, text)

    async def submit(self, key, user_id, username, display_name, text, admins):
        async with self.payments.transaction() as db:
            await self.schema(db)
            old = await self.payments._one(db, 'SELECT ticket FROM support_operations WHERE chat_id=? AND message_id=?', key)
            if old:
                return old['ticket'], []
            text = checked_text(text)
            if not await self.payments._one(db, 'SELECT 1 FROM support_sessions WHERE user_id=? AND chat_id=?', (user_id, key[0])):
                raise PaymentError(SAFE_ERROR)
            if await self.payments._one(db, "SELECT 1 FROM support_tickets WHERE user_id=? AND status='open'", (user_id,)):
                raise PaymentError('У вас уже есть открытое обращение. Дождитесь ответа поддержки.')
            now = int(time.time())
            recent = await self.payments._one(db, 'SELECT MAX(created_at) AS latest FROM support_tickets WHERE user_id=?', (user_id,))
            if recent['latest'] is not None and now - recent['latest'] < COOLDOWN:
                raise PaymentError('Подождите несколько минут перед новым обращением.')
            number = secrets.token_hex(5).upper()
            username = SENSITIVE.sub('[скрыто]', (username or '')[:64])
            display_name = SENSITIVE.sub('[скрыто]', (display_name or 'Пользователь')[:128])
            await db.execute("INSERT INTO support_tickets VALUES (?,?,?,?,?,'open',?,?)", (number, user_id, username, display_name, text, now, now))
            await db.execute('INSERT INTO support_operations VALUES (?,?,?,?,?)', (*key, 'create', number, now))
            await db.execute('DELETE FROM support_sessions WHERE user_id=?', (user_id,))
            notice = (f'Новое обращение по оплате №{number}\nПользователь: '
                      f'{"@" + username if username else display_name}\nTelegram ID: {user_id}\n'
                      f'Сообщение: {text}\n\nДля ответа:\n/replyticket {number} текст ответа')
            outgoing = [await self._outgoing(db, number, admin, notice) for admin in sorted(admins)]
            return number, outgoing

    async def act(self, key, number, *, reply=None):
        if not re.fullmatch(r'[A-F0-9]{10}', number):
            raise PaymentError(SAFE_ERROR)
        async with self.payments.transaction() as db:
            await self.schema(db)
            if await self.payments._one(db, 'SELECT 1 FROM support_operations WHERE chat_id=? AND message_id=?', key):
                return []
            row = await self.payments._one(db, "SELECT * FROM support_tickets WHERE number=? AND status='open'", (number,))
            if not row:
                raise PaymentError(SAFE_ERROR)
            now = int(time.time())
            if reply is not None:
                reply = checked_text(reply)
                text = f'Ответ поддержки по обращению №{number}\n\n{reply}'
                kind = 'reply'
            else:
                text = f'Обращение №{number} закрыто.'
                kind = 'close'
                await db.execute("UPDATE support_tickets SET status='closed' WHERE number=?", (number,))
            await db.execute('UPDATE support_tickets SET updated_at=? WHERE number=?', (now, number))
            await db.execute('INSERT INTO support_operations VALUES (?,?,?,?,?)', (*key, kind, number, now))
            return [await self._outgoing(db, number, row['user_id'], text)]

    async def delivered(self, operation_id, success):
        async with self.payments.transaction() as db:
            await self.schema(db)
            await db.execute("UPDATE support_messages SET status=?,updated_at=? WHERE id=? AND status='claimed'", ('sent' if success else 'uncertain', int(time.time()), operation_id))

    async def open_tickets(self):
        async with self.payments.transaction() as db:
            await self.schema(db)
            async with db.execute("SELECT number,user_id,username,display_name,text FROM support_tickets WHERE status='open' ORDER BY created_at DESC LIMIT 10") as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def count(self):
        async with self.payments.transaction() as db:
            await self.schema(db)
            row = await self.payments._one(db, "SELECT COUNT(*) AS n FROM support_tickets WHERE status='open'")
            return row['n']

    async def is_submission(self, key):
        if not self.payments.exists:
            return False
        async with self.payments.transaction() as db:
            await self.schema(db)
            return bool(await self.payments._one(db, 'SELECT 1 FROM support_operations WHERE chat_id=? AND message_id=? AND kind=?', (*key, 'create')))
