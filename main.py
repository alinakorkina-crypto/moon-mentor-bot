from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
import asyncio

BOT_TOKEN = "88814424563:AAHF4QryY62RgMC0uI9Y049g-70JEkaKSEk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_command(message: Message):
    await message.answer(
        "🌙 Добро пожаловать в Moon Mentor!\n\n"
        "Я ИИ-наставник для самопознания через символику Таро."
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())