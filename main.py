from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
import asyncio

BOT_TOKEN = "8814424563:AAFm7hLoFPPS5-piyIFkmx0MwLsFs7pCGA8"

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