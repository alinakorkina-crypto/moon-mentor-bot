"""Payment support routing. Plain text only; no analytics or model calls."""
import os

from payments_service import PaymentError
from support_service import SupportService, UNAVAILABLE


async def deliver(service, bot, outgoing):
    for operation_id, recipient, text in outgoing:
        success = False
        try:
            await bot.send_message(recipient, text, parse_mode=None)
            success = True
        except Exception:
            # Delivery may have succeeded remotely. Never automatically resend.
            pass
        try:
            await service.delivered(operation_id, success)
        except PaymentError:
            pass  # Durable pre-send claim still prevents duplicate delivery.


async def handle_support(message, *, payments, bot, admins, user_mode, menu):
    text = message.text or ''
    command = text.split(maxsplit=1)[0].split('@')[0] if text else ''
    commands = {'/paysupport', '/replyticket', '/closeticket', '/tickets'}
    user_id = message.from_user.id
    key = (message.chat.id, message.message_id)
    service = SupportService(payments)
    try:
        if command in commands:
            # Support and its private content are never published in group chats.
            chat_type = getattr(message.chat, 'type', 'private')
            if chat_type != 'private':
                await message.answer('Откройте личный чат с Moon Mentor для обращения в поддержку.', parse_mode=None)
                return True
            if command == '/paysupport':
                user_mode[user_id] = None
                answer = await service.start(user_id, message.chat.id)
                contact = os.getenv('PAY_SUPPORT_CONTACT', '').strip()
                if contact:
                    answer += '\n\nДополнительный контакт: ' + contact
                await message.answer(answer, parse_mode=None)
                return True
            if user_id not in admins:
                await message.answer('Команда недоступна.', parse_mode=None)
                return True
            if command == '/tickets':
                rows = await service.open_tickets()
                if not rows:
                    await message.answer('Открытых обращений нет.', parse_mode=None)
                for row in rows:
                    await message.answer(f"№{row['number']} | {row['user_id']} | "
                                         f"{row['username'] or row['display_name']}\n{row['text'][:200]}", parse_mode=None)
                return True
            parts = text.split(maxsplit=2)
            if len(parts) < 2 or (command == '/replyticket' and len(parts) < 3) or (command == '/closeticket' and len(parts) != 2):
                raise PaymentError('Проверьте номер обращения и текст команды.')
            outgoing = await service.act(key, parts[1], reply=parts[2] if command == '/replyticket' else None)
            await deliver(service, bot, outgoing)
            await message.answer('Операция сохранена. Повтор команды не создаёт новую отправку.', parse_mode=None)
            return True
        # A redelivered creation message must not fall through to a reading.
        if await service.is_submission(key):
            return True
        if not await service.waiting(user_id, message.chat.id):
            return False
        navigation = {button.text for row in menu.keyboard for button in row}
        navigation |= {'⬅️ Главное меню', '💭 Свой вопрос', '❤️ Отношения', '💼 Карьера',
                       '🃏 Карта дня', '🌙 Полный расклад', '🌙 Для чего нужен Moon', '🔮 Как работают расклады'}
        if text.startswith('/') or text in navigation:
            await service.cancel(user_id)
            return False
        if not text:
            await message.answer('Отправьте описание проблемы текстом, до 1500 символов.', parse_mode=None)
            return True
        number, outgoing = await service.submit(key, user_id,
            getattr(message.from_user, 'username', ''), getattr(message.from_user, 'full_name', ''), text, admins)
        user_mode[user_id] = None
        await deliver(service, bot, outgoing)
        await message.answer(f'Обращение №{number} передано. Ответ придёт сюда, в Moon Mentor.',
                             parse_mode=None, reply_markup=menu)
        return True
    except PaymentError as error:
        # Only locally defined safe errors; never include Telegram exception data.
        safe = str(error) if type(error) is PaymentError else UNAVAILABLE
        await message.answer(safe, parse_mode=None)
        return True
