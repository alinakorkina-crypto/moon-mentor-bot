# Telegram Stars MVP

The default is `PAYMENTS_ENABLED=false`. With payments disabled, the existing
menus, replies and reading paths are unchanged. No payment database is opened
by ordinary reading/navigation requests. `READING_ENGINE=legacy` is not metered.
The new limit applies only to v8 question/love/career readings. Daily card, full
spread and Moon chat keep their existing behavior.

## Configuration

- `PAYMENTS_ENABLED=true` enables sales, balance UI and v8 credit accounting.
- `PAYMENT_PAYLOAD_SECRET` is a separate persistent signing secret, not the bot
  token. Empty/service-placeholder secrets fail closed: v8 does not run for free.
- `PAYMENTS_DB_PATH` defaults to `payments.sqlite3`. Keep it on persistent local
  storage, preferably outside the checkout. Back up the ledger and signing secret
  together. If using a custom filename inside the checkout, ensure it is ignored.
- `PAY_SUPPORT_CONTACT` optionally supplies the support contact shown by
  `/paysupport` in addition to the built-in ticket workflow; no public personal
  contact or separate support account is required.
- `ADMIN_IDS` controls payment ticket replies/closure, `/tickets`,
  `/refundstars <charge_id>` and the existing admin stats.
- Continue using standard `OPENAI_API_KEY` and existing transport/model settings.

Changing these variables requires process restart. Disabling sales does not
invalidate existing invoices: pre-checkout and successful payment still work.
If the signing secret is absent or a service placeholder, new sales fail closed,
but an existing exact opaque invoice token can be verified against the durable
ledger, its owner and catalog values. Keep the original secret backed up and do
not replace it with a different nonempty key while invoices are outstanding.
Never reuse `BOT_TOKEN` as the payload secret. No real credentials belong in Git.
Relative database paths are resolved once against the working directory at
service creation. Absolute paths remain absolute.

## Product and user path

Every user gets three free credits once, including existing users on their first
ledger access. Free credits are reserved first, then paid credits. Packages are
defined server-side: 1 for 50 XTR, 5 for 200 XTR, 10 for 350 XTR. All invoices use
XTR, one price entry, and omit `provider_token`.

After the free balance is exhausted the bot offers purchase buttons without
drawing cards or invoking AI. The user selects a package, pays a signed,
user-bound invoice and receives an updated balance. They then select a reading
mode and send a new question. `/balance` and “🌙 Мой баланс” show free and paid
credits separately; “⭐ Купить расклады” opens the three package buttons.

## SQLite ledger

All mutations use `BEGIN IMMEDIATE`, foreign keys, bounded busy timeouts and
parameterized values. Initial schema creation is idempotent; it never resets
users' free credits. The database uses SQLite's normal journal mode. Database,
journal, WAL/SHM and common SQLite temporary file names are ignored by Git.

- `users`: user ID, available free/paid credits, refund debt, timestamps.
- `invoices`: unique opaque payload/nonce, user ID, package, 15-minute expiry,
  checkout ID and approval time, issued/approved/expired/cancelled/paid lifecycle.
  The original issued/paid status column is retained for additive migration.
- `purchases`: unique Telegram charge ID, unique invoice payload, user ID, Stars,
  credits, paid/refund_pending/refunded state and refund timestamp.
- `reading_reservations`: unique `(chat_id, message_id)`, owner, free/paid source,
  reserved/completed/released state, durable successful result/cards/question,
  history/delivery markers and timestamps.
- `payment_audit`: rejection code, hashed reference and timestamp; no payload,
  charge ID or credentials. Conflicting updates are committed here even when
  their business mutation is rejected.

Payloads contain a random nonce and a 128-bit truncated HMAC-SHA256 tag. The tag
binds the nonce, user and fixed package, and is checked with `compare_digest`.
Length/format, stored invoice, owner, currency and amount are checked at checkout
and again at successful payment. A charge ID or invoice cannot grant credit twice.
An approved checkout ID cannot be rebound to another invoice, and another checkout
ID cannot reuse that approved invoice. Duplicate delivery of the same query is
answered once per update without granting credits. New checkouts for expired,
cancelled or paid invoices are rejected. Cancellation is allowed only before
checkout approval. A successful payment authorized before expiry is accepted
even when its service update arrives after expiry; this is not a new checkout.
Successful-payment duplicates remain harmless after expiry. The full Telegram
charge ID is retained in SQLite without truncation, never in general output.
Do not export ledger rows into ordinary logs: they contain private user/payment
data. Public statistics are aggregate only; Stars and credit issuance are gross
lifetime totals, with refund counts reported separately.

## Reservation lifecycle and delivery

Before drawing cards, an atomic reservation reduces **available** balance by one.
It is not counted as a used credit until a successful v8 result. The result and
the `completed` status are committed together before Telegram delivery. An
error/rejection/timeout/invalid JSON releases the reservation and credits the
same source exactly once. Released paid credit first settles any refund debt.

One shielded per-message task owns reserve → generate → finalize. Cancelling the
Telegram handler does not cancel this task, so the eventual model outcome still
completes/releases the credit. Duplicate messages cannot draw or generate again.
A Telegram send failure does not release a completed credit or regenerate; it
reuses the same cards/text. Successful results are stored in SQLite, allowing
delivery restoration after process-cache loss. History uses the existing
at-most-once marker behavior; a filesystem failure during history writing can
leave incomplete history and must not trigger another AI request.
Lookup in SQLite occurs before the message's navigation-state dispatch, so a
restart does not require a surviving `user_mode` entry. Completed operations are
restored even with sales disabled or the signing secret absent. A process crash
between sending an image/text and marking delivery can repeat Telegram output;
it cannot repeat generation or debit.

After a process crash, a still-`reserved` operation has an unknown model outcome.
It is not regenerated or blindly released: support must reconcile it. The
in-process task cache lasts until restart, as in the existing reading service.

## Refunds

Only admins can use `/refundstars <charge_id>`. A transaction claims the purchase
as `refund_pending` before calling `Bot.refund_star_payment`. A positive result
marks it refunded and removes the originally purchased credits. If some credits
are no longer available, the difference becomes debt. Future paid credits pay
this debt before increasing spendable balance. Free credits are not removed.

Duplicate admin commands never submit a second refund. If Telegram times out or
the process stops between the external refund and local finalization, the claim
remains pending. The command reports that manual verification is required.
After independently verifying a successful refund, a maintainer can finalize the
same charge with the idempotent `PaymentsService.complete_refund` method. Never
reset pending claims or repeat the external refund based only on a timeout.

## Administrative diagnostics and manual reconciliation

`/paymentdiag` is restricted to `ADMIN_IDS`, including when sales are disabled.
It reports counts of `reserved`, `refund_pending`, rejection events, and up to
20 oldest opaque references/timestamps per pending category. It never resolves
business states automatically or prints user questions, payloads, credentials,
full charge IDs, or support contacts. References are generated by
`PaymentsService.reference('reading', f'{chat_id}:{message_id}')` and
`PaymentsService.reference('refund', charge_id)`.

Manual procedure (maintenance only; no automatic provider requests):

1. Stop/quiesce all bot workers and verify there is no live generation/refund
   task for the operation. Securely back up SQLite using its backup API and keep
   the original signing secret. Do not copy only an active WAL database file.
2. Match the diagnostic reference to the private ledger locally using the
   reference functions above. Read the full key/charge only in this restricted
   maintenance session; never paste it or payloads into ordinary logs. Record
   evidence and the administrator's decision in a restricted support ticket.
3. For `reserved`, verify whether a validated result was saved/delivered or the
   attempt definitely failed. If failure is established, call
   `await service.finish((chat_id, message_id), success=False)` once. It returns
   the same free/paid source transactionally. If a valid original result/cards
   are recoverable, call `finish(..., success=True, result={"text": original_text,
   "mode": original_mode, "question": original_question, "cards": original_cards})`
   with the actual original values after local v8 validation. Never regenerate
   the same operation. If evidence is
   insufficient, leave it reserved and resolve with support rather than guessing.
4. For `refund_pending`, independently verify the actual Telegram refund. Only
   after a confirmed refund call `await service.complete_refund(charge_id)`.
   This finishes the existing claim and debt adjustment without another Bot API
   call. If uncertain/failed, leave the claim pending and resolve through support;
   do not reset it to paid or blindly repeat the refund.
5. Re-read balance, operation/purchase state and `/paymentdiag`, verify the
   expected transition and resume workers. Repeating terminal local finalizers
   is harmless; repeating an external refund is not permitted.

Invoice initialization/migration is additive (`user_version=2`). It preserves
free balances, purchases, issued/paid invoices and their original expiry across
reinitialization. The checker adds missing fields and unique nonce/checkout
indexes but never resets balances or automatically releases pending operations.

## Exact user-facing payment messages

- Initial balance: `🌙 Ваш баланс`, then `Бесплатные: 3`, `Купленные: 0`,
  `Всего доступно: 3` on separate lines.
- After the third successful free reading, a separately stored footer says:
  `Это был последний бесплатный расклад. Продолжить можно после покупки пакета за Stars.`
  If paid credit is already available: `Это был последний бесплатный расклад. Следующие будут использовать купленные кредиты.`
- Exhausted: `Бесплатные расклады закончились. Купите пакет, чтобы продолжить.`
- Success: `Покупка учтена.` followed by the current balance, only after commit.
- Duplicate: `Эта покупка уже учтена. Баланс не изменён.` plus current balance.
- Unavailable: `Сейчас покупка и платные расклады недоступны. Попробуйте немного позже.`
- Model failure after committed release:
  `Сейчас не удалось подготовить трактовку. Попробуйте немного позже.`
  No uncommitted refund is promised; if ledger finalization fails, show unavailable.
- Support: built-in `/paysupport` tickets (see below).

## Offline verification

Use the exact versions from `requirements-server-test.txt` in a separate venv,
then run `python -B run_tests_offline.py`. The suite blocks sockets and real
subprocesses, uses real aiogram types with mocked Telegram/model methods, and
exercises SQLite concurrency with temporary ledgers. No tests submit payments,
refunds, invoices or live model requests.


## Built-in private payment support

`/paysupport` works regardless of `PAYMENTS_ENABLED` and without a signing secret.
It asks for one text message (maximum 1500 characters), warns against sharing card
details/passwords/codes, and persists the waiting session. Recognizable card
numbers, credentials, invoice payloads and explicitly labelled passwords/codes
are rejected before storage. This filter cannot identify every secret in free
text: administrators must treat the ledger and backups as private personal data.
An optional `PAY_SUPPORT_CONTACT` is only an additional plain-text contact.

The next message creates a random 10-hex-digit public ticket number, clears the
support session and restores the usual keyboard. There is at most one open ticket
per user (unique partial index) and a five-minute interval between ticket creation
times, including after closure. Commands/menu navigation cancel a waiting session.
Support messages never enter reading generation, credit accounting or analytics.
Support commands accept private chats only.

All existing `ADMIN_IDS` receive a plain-text notification with the ticket,
user identity and description. `/tickets` is admin-only and shows at most ten
open tickets, with a 200-character preview. `/replyticket NUMBER reply` sends a
reply of at most 1500 characters to the ticket owner. `/closeticket NUMBER` closes
it and notifies the owner. Unknown/closed/invalid tickets return neutral errors.
`/paymentdiag` adds only an aggregate open-ticket count, never ticket content.

Tables are created additively in the same ledger transaction:

- `support_sessions`: user ID (PK), chat ID, creation time; survives restarts.
- `support_tickets`: random number (PK), user ID, username/display name, original
  description, open/closed status, creation/update times; one open per user.
- `support_operations`: Telegram `(chat_id,message_id)` (PK), operation kind,
  ticket FK and creation time; deduplicates creation/reply/closure across restarts.
- `support_messages`: ticket FK, recipient, plain text, claimed/sent/uncertain
  status and creation/update times. Contains notifications and outgoing replies.

Each operation and its outgoing delivery claims are committed before any Telegram
send. Only the transaction creating a claim may send it; concurrent/replayed
commands return no outgoing messages. A failure, timeout, crash or cancellation
can leave a claimed/uncertain message: **it is never automatically resent**, even
if its delivery outcome is unknown. This prioritizes avoiding duplicate replies
and may lose a notification. Admins can inspect `/tickets`; after checking the
conversation they can intentionally issue a new reply (a new Telegram message).
Never blindly replay uncertain sends or reset operation records. An acknowledgement
failure also leaves the created ticket intact and cannot start a reading on retry.
No support content/identities are logged or included in general analytics.
