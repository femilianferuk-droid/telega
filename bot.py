#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Bot для управления сессиями Pyrogram на Aiogram
API данные уже встроены, токен из переменных окружения
"""

import os
import sys
import re
import json
import asyncio
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

# Импортируем aiogram
try:
    from aiogram import Bot, Dispatcher, types, F
    from aiogram.filters import Command
    from aiogram.types import Message
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
except ImportError as e:
    print(f"❌ Ошибка импорта aiogram: {e}")
    print("📦 Установите: pip install aiogram==3.10.0")
    sys.exit(1)

# Импортируем pyrogram
try:
    from pyrogram import Client
    from pyrogram.errors import Unauthorized, AuthKeyUnregistered, SessionPasswordNeeded
    import pyrogram
except ImportError as e:
    print(f"❌ Ошибка импорта pyrogram: {e}")
    print("📦 Установите: pip install pyrogram tgcrypto")
    sys.exit(1)

# API данные (встроены в код)
API_ID = 32480523
API_HASH = "147839735c9fa4e83451209e9b55cfc5"

# Токен бота из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: Не найден токен бота в переменных окружения")
    print("📝 Установите: export BOT_TOKEN='ваш_токен'")
    sys.exit(1)

# Директории
SESSION_DIR = Path("sessions")
SESSION_DIR.mkdir(exist_ok=True)

# Хранилище сессий пользователей
user_sessions: Dict[int, Dict] = {}


def setup_termux():
    """Настройка окружения для Termux"""
    if 'com.termux' in os.environ.get('PREFIX', ''):
        print("📱 Termux обнаружен")
        SESSION_DIR.mkdir(exist_ok=True)
        print("✅ Директория создана")


# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()


@dp.message(Command("start"))
async def start_command(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 *Привет! Я бот для управления сессиями Pyrogram*\n\n"
        "📤 *Просто отправь мне файл .session* - я покажу номер телефона\n"
        "🔍 */code* - получить последний код подтверждения\n"
        "ℹ️ */info* - информация о сессии\n"
        "❌ */clear* - удалить сессию\n\n"
        "⚡️ *Как использовать:*\n"
        "1. Создай сессию в Pyrogram\n"
        "2. Отправь файл .session мне\n"
        "3. Используй /code для получения кодов"
    )


@dp.message(Command("info"))
async def info_command(message: Message):
    """Обработчик команды /info"""
    user_id = message.from_user.id
    
    if user_id in user_sessions:
        session = user_sessions[user_id]
        
        # Проверяем существование файла
        session_path = Path(session["session_path"])
        file_exists = "✅" if session_path.exists() else "❌"
        file_size = session_path.stat().st_size if session_path.exists() else 0
        
        await message.answer(
            f"ℹ️ *Информация о сессии*\n\n"
            f"📱 *Номер:* `{session['phone']}`\n"
            f"👤 *Имя:* {session.get('first_name', 'Неизвестно')} {session.get('last_name', '')}\n"
            f"🆔 *Telegram ID:* `{session.get('user_id', 'Неизвестно')}`\n"
            f"📁 *Файл:* {file_exists} `{session_path.name}`\n"
            f"📊 *Размер:* {file_size} bytes\n"
            f"📅 *Статус:* {'Активна' if file_exists == '✅' else 'Файл не найден'}"
        )
    else:
        await message.answer("❌ *У вас нет загруженной сессии*\n\nОтправьте файл .session")


@dp.message(Command("clear"))
async def clear_command(message: Message):
    """Обработчик команды /clear"""
    user_id = message.from_user.id
    
    if user_id in user_sessions:
        session_data = user_sessions[user_id]
        
        # Удаляем файл сессии
        session_path = Path(session_data["session_path"])
        if session_path.exists():
            session_path.unlink()
        
        # Удаляем из памяти
        del user_sessions[user_id]
        
        # Удаляем связанные файлы
        for f in SESSION_DIR.glob(f"user_{user_id}_*.session"):
            f.unlink()
        for f in SESSION_DIR.glob(f"user_{user_id}_*.session-journal"):
            if f.exists():
                f.unlink()
        for f in SESSION_DIR.glob(f"user_{user_id}_*.session-journal"):
            if f.exists():
                f.unlink()
        
        await message.answer("✅ *Сессия очищена*\n\nВсе файлы удалены")
    else:
        await message.answer("ℹ️ *Нет активной сессии для очистки*")


@dp.message(Command("code"))
async def code_command(message: Message):
    """Обработчик команды /code"""
    user_id = message.from_user.id
    
    # Проверка наличия сессии
    if user_id not in user_sessions:
        await message.answer(
            "❌ *Сессия не найдена*\n\n"
            "Сначала отправьте файл .session"
        )
        return

    session_data = user_sessions[user_id]
    status_msg = await message.answer("🔍 *Поиск кода подтверждения...*")

    try:
        # Подключение к аккаунту
        client = Client(
            name=session_data["session_name"],
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=str(SESSION_DIR)
        )
        
        await client.start()
        
        # Поиск последнего личного чата
        dialogs = []
        async for dialog in client.get_dialogs():
            if dialog.chat.type == "private":
                dialogs.append(dialog)
        
        if not dialogs:
            await status_msg.edit_text("❌ *Личные чаты не найдены*")
            await client.stop()
            return
        
        # Берем первый (самый новый) диалог
        latest_dialog = dialogs[0]
        chat_name = latest_dialog.chat.first_name or latest_dialog.chat.title or "Пользователь"
        
        # Получаем последние сообщения
        messages = []
        async for msg in client.get_chat_history(latest_dialog.chat.id, limit=30):
            messages.append(msg)
        
        # Поиск кода (5-6 цифр)
        code_pattern = r'\b\d{5,6}\b'
        
        for msg in messages:
            if not msg.outgoing and msg.text:
                codes = re.findall(code_pattern, msg.text)
                if codes:
                    code = codes[0]
                    
                    # Определяем отправителя
                    sender_name = "Неизвестно"
                    if msg.from_user:
                        sender_name = msg.from_user.first_name or "Пользователь"
                    
                    # Форматируем текст сообщения
                    msg_text = msg.text
                    if len(msg_text) > 200:
                        msg_text = msg_text[:200] + "..."
                    
                    # Отправляем результат
                    result_text = (
                        f"✅ *Найден код подтверждения!*\n\n"
                        f"🔢 *Код:* `{code}`\n"
                        f"💬 *От:* {sender_name}\n"
                        f"📝 *Текст:* {msg_text}\n"
                    )
                    
                    # Если есть клавиатура или кнопки в сообщении, показываем полную информацию
                    if msg.reply_markup:
                        result_text += f"\n📋 *Есть клавиатура в сообщении*"
                    
                    await status_msg.edit_text(result_text)
                    
                    await client.stop()
                    return
        
        await status_msg.edit_text(
            f"❌ *Код не найден*\n\n"
            f"Проверено {len(messages)} последних сообщений в чате с {chat_name}"
        )
        
        await client.stop()

    except Unauthorized:
        await status_msg.edit_text(
            "❌ *Сессия устарела*\n\n"
            "Отправьте новую сессию."
        )
        if user_id in user_sessions:
            del user_sessions[user_id]
            
    except Exception as e:
        await status_msg.edit_text(
            f"❌ *Ошибка*\n\n"
            f"`{str(e)}`"
        )


@dp.message(F.document)
async def handle_document(message: Message):
    """Обработчик загруженных файлов"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    document = message.document
    
    # Проверка расширения файла
    if not document.file_name.endswith('.session'):
        await message.answer(
            "❌ *Неверный формат*\n\n"
            "Отправьте файл с расширением `.session`"
        )
        return

    # Скачивание файла
    session_filename = f"user_{user_id}_{document.file_name}"
    session_path = SESSION_DIR / session_filename
    
    # Показываем прогресс
    progress_msg = await message.answer("⏳ *Загрузка файла...*")
    
    try:
        # Скачиваем файл
        file = await bot.get_file(document.file_id)
        await file.download(destination=session_path)
        
        await progress_msg.edit_text("🔄 *Подключение к аккаунту...*")

        # Попытка подключения с загруженной сессией
        session_name = str(session_path.with_suffix(''))
        
        # Создаем временного клиента для проверки сессии
        temp_client = Client(
            name=session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=str(SESSION_DIR),
            in_memory=False
        )
        
        await temp_client.start()
        
        # Получение информации об аккаунте
        me = await temp_client.get_me()
        phone_number = me.phone_number
        
        # Сохранение данных сессии
        user_sessions[user_id] = {
            "session_name": session_name,
            "phone": phone_number,
            "session_path": str(session_path),
            "user_name": user_name,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "user_id": me.id
        }
        
        await temp_client.stop()
        
        await progress_msg.edit_text(
            f"✅ *Сессия успешно загружена!*\n\n"
            f"📱 *Номер:* `{phone_number}`\n"
            f"👤 *Имя:* {me.first_name or ''} {me.last_name or ''}\n"
            f"🆔 *ID:* `{me.id}`\n\n"
            f"Теперь отправьте `/code` чтобы получить код подтверждения"
        )

    except Unauthorized:
        await progress_msg.edit_text(
            "❌ *Сессия недействительна*\n\n"
            "Сессия устарела или была завершена."
        )
        if session_path.exists():
            session_path.unlink()
            
    except Exception as e:
        await progress_msg.edit_text(
            f"❌ *Ошибка подключения*\n\n"
            f"Причина: `{str(e)}`"
        )
        if session_path.exists():
            session_path.unlink()


@dp.message()
async def handle_text(message: Message):
    """Обработчик текстовых сообщений"""
    if message.text and not message.text.startswith('/'):
        await message.answer(
            "❓ *Неизвестная команда*\n\n"
            "Используйте:\n"
            "/start - начать\n"
            "/code - получить код\n"
            "/info - информация\n"
            "/clear - очистить"
        )


async def main():
    """Основная функция запуска бота"""
    print("\n" + "="*50)
    print("🚀 ЗАПУСК TELEGRAM BOT (Aiogram)")
    print("="*50)
    
    # Настройка для Termux
    setup_termux()
    
    print("\n✅ Конфигурация:")
    print(f"🔑 API ID: {API_ID}")
    print(f"🔐 API Hash: {API_HASH[:10]}...")
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"📁 Директория сессий: {SESSION_DIR.absolute()}")
    print("="*50)
    
    print("\n🤖 Бот запущен и готов к работе!")
    print("📱 Откройте Telegram и отправьте /start")
    print("="*50 + "\n")
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n\n👋 Бот остановлен")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
