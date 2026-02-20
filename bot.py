import asyncio
import re
import os
import sys
import logging
import random
import json
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    FloodWait,
    PhoneNumberInvalid, PhoneCodeInvalid, PasswordHashInvalid,
    SessionPasswordNeeded, ApiIdInvalid, AccessTokenInvalid
)
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Конфигурация из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "user_session"

# Маскировка под человека - человеческие задержки
HUMAN_DELAYS = {
    "typing": (1, 3),  # задержка перед ответом
    "action": (2, 5),  # задержка между действиями
    "long": (5, 10),   # длительная задержка
    "very_long": (15, 30)  # очень длительная задержка
}

# Человеческие фразы для разных ситуаций
HUMAN_PHRASES = {
    "start": [
        "Привет! Чем могу помочь?",
        "Здравствуйте! Я к вашим услугам.",
        "Добрый день! Что будем делать?",
        "Приветствую! Готов к работе.",
        "Слушаю вас внимательно."
    ],
    "thinking": [
        "Секунду...",
        "Минутку...",
        "Дайте подумать...",
        "Обрабатываю запрос...",
        "Ща все сделаем..."
    ],
    "done": [
        "Готово!",
        "Сделано!",
        "Выполнено!",
        "Все готово!",
        "Принято!"
    ],
    "error": [
        "Что-то пошло не так...",
        "Ошибка вышла...",
        "Не получилось :(",
        "Попробуйте еще раз?",
        "Что-то сломалось..."
    ],
    "wait": [
        "Нужно немного подождать...",
        "Тормозит телеграм...",
        "Секундочку...",
        "Загружаю..."
    ]
}

# Проверяем наличие токена при запуске
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
    print("Создайте файл .env и добавьте строку: BOT_TOKEN=ваш_токен")
    sys.exit(1)

# Глобальные переменные
user_state = {}
user_data = {}
user_clients = {}
user_activity = {}
user_chat_history = {}  # История диалога для каждого пользователя

# Человеческие кнопки (без ботовского вида)
main_keyboard = ReplyKeyboardMarkup(
    [
        ["📢 Создать канал", "👥 Создать группу"],
        ["⚙️ Настройки", "❓ Помощь"]
    ],
    resize_keyboard=True
)

# Функция для человеческой задержки
async def human_delay(delay_type="action"):
    """Имитирует человеческую задержку"""
    if delay_type in HUMAN_DELAYS:
        min_delay, max_delay = HUMAN_DELAYS[delay_type]
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

# Функция для имитации печатания
async def simulate_typing(client, chat_id, duration=None):
    """Имитирует набор текста человеком"""
    if not duration:
        duration = random.uniform(1, 3)
    
    await client.send_chat_action(chat_id, "typing")
    await asyncio.sleep(duration)

# Функция для получения человеческой фразы
def get_human_phrase(phrase_type):
    """Возвращает случайную человеческую фразу"""
    if phrase_type in HUMAN_PHRASES:
        return random.choice(HUMAN_PHRASES[phrase_type])
    return "..."

# Функция для сохранения истории диалога
def save_to_history(user_id, message, response):
    """Сохраняет диалог в историю"""
    if user_id not in user_chat_history:
        user_chat_history[user_id] = []
    
    user_chat_history[user_id].append({
        "time": datetime.now().isoformat(),
        "message": message,
        "response": response
    })
    
    # Ограничиваем историю
    if len(user_chat_history[user_id]) > 50:
        user_chat_history[user_id] = user_chat_history[user_id][-50:]

# Обработчик команды /start (маскируем под обычное сообщение)
async def start_command(client, message):
    user_id = message.from_user.id
    
    # Человеческая задержка перед ответом
    await human_delay("typing")
    await simulate_typing(client, message.chat.id)
    
    # Приветствие как у человека
    welcome_text = (
        f"{get_human_phrase('start')}\n\n"
        f"Я помогу создать каналы и группы. "
        f"Сколько нужно создать сегодня?"
    )
    
    await message.reply(welcome_text, reply_markup=main_keyboard)
    
    # Сохраняем в историю
    save_to_history(user_id, "/start", welcome_text)
    
    user_state[user_id] = "main_menu"

# Обработчик главного меню (человеческие ответы)
async def handle_main_menu(client, message):
    user_id = message.from_user.id
    text = message.text.lower()
    
    # Человеческая задержка
    await human_delay("typing")
    await simulate_typing(client, message.chat.id)
    
    if "канал" in text:
        response = "Понял, создаем каналы. Какое название дадим?"
        await message.reply(response)
        
        save_to_history(user_id, message.text, response)
        user_state[user_id] = "channel_name"
        
    elif "групп" in text:
        response = "Хорошо, создаем группы. Как назовем?"
        await message.reply(response)
        
        save_to_history(user_id, message.text, response)
        user_state[user_id] = "group_name"
        
    elif "настройк" in text:
        response = "⚙️ Настройки пока в разработке. Что именно интересует?"
        await message.reply(response)
        
    elif "помощ" in text:
        response = (
            "❓ **Как работать:**\n\n"
            "1. Нажми «Создать канал»\n"
            "2. Введи название\n"
            "3. Укажи количество\n"
            "4. Готово!\n\n"
            "Если что-то непонятно - спрашивай"
        )
        await message.reply(response)
        
    else:
        response = "Не понял команду. Выбери пункт из меню 👇"
        await message.reply(response, reply_markup=main_keyboard)

# Обработчик создания каналов (маскировка под человека)
async def handle_channel_creation(client, message):
    user_id = message.from_user.id
    text = message.text
    
    # Человеческая задержка
    await human_delay("typing")
    await simulate_typing(client, message.chat.id)
    
    state = user_state.get(user_id)
    
    if state == "channel_name":
        user_data[user_id] = {"channel_base_name": text}
        response = f"Принял. Название: {text}\n\nСделаем каналы публичными или приватными?"
        await message.reply(response)
        user_state[user_id] = "channel_public"
        
    elif state == "channel_public":
        if "да" in text.lower() or "публичн" in text.lower():
            user_data[user_id]["channel_public"] = True
            response = "Ок, публичные. Какой username использовать? (например: my_channel)"
            await message.reply(response)
            user_state[user_id] = "channel_username"
        else:
            user_data[user_id]["channel_public"] = False
            response = "Понял, приватные. Сколько каналов создать?"
            await message.reply(response)
            user_state[user_id] = "channel_count"
            
    elif state == "channel_username":
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', text):
            user_data[user_id]["channel_base_username"] = text
            response = f"Username {text} принят. Сколько каналов создаем?"
            await message.reply(response)
            user_state[user_id] = "channel_count"
        else:
            response = "Неверный формат username. Используй только буквы, цифры и _. Начни с буквы."
            await message.reply(response)
            
    elif state == "channel_count":
        try:
            count = int(text)
            if 1 <= count <= 20:  # Ограничиваем до 20 для безопасности
                user_data[user_id]["channel_count"] = count
                response = f"{count} каналов. Отлично! Начинаю создание...\nЭто займет некоторое время."
                await message.reply(response)
                
                # Человеческая задержка перед началом
                await human_delay("long")
                
                # Создаем каналы
                await create_channels_with_delay(client, message, user_id)
            else:
                response = "Слишком много. Давай не больше 20 за раз."
                await message.reply(response)
        except ValueError:
            response = "Это не число. Введи количество цифрами."
            await message.reply(response)

# Функция создания каналов с человеческими задержками
async def create_channels_with_delay(client, message, user_id):
    """Создает каналы с имитацией человеческого поведения"""
    
    await message.reply(get_human_phrase('thinking'))
    await human_delay("long")
    
    # Получаем клиент пользователя
    user_client = await get_user_client(user_id)
    if not user_client:
        await message.reply("❌ Нужно авторизоваться сначала. Напиши /start")
        return
    
    created = 0
    errors = 0
    
    for i in range(1, user_data[user_id]["channel_count"] + 1):
        try:
            # Человеческая задержка между созданиями
            if i > 1:
                delay = random.uniform(15, 30)  # Большая задержка как у человека
                await message.reply(f"⏳ Создаю {i}-й канал... Подожди немного...")
                await asyncio.sleep(delay)
            
            # Формируем название
            channel_title = f"{user_data[user_id]['channel_base_name']} {i}"
            
            if user_data[user_id].get("channel_public"):
                username = f"{user_data[user_id]['channel_base_username']}{i if i > 1 else ''}"
            else:
                username = None
            
            # Создаем канал
            channel = await user_client.create_channel(
                title=channel_title,
                description=f"Канал создан {datetime.now().strftime('%d.%m.%Y')}",
                username=username
            )
            
            created += 1
            
            # Не показываем все подряд, как человек
            if i % 3 == 0 or i == user_data[user_id]["channel_count"]:
                await message.reply(f"✅ Создано {created} каналов. Продолжаем...")
            
        except FloodWait as e:
            wait_time = e.value
            await message.reply(f"⏳ Телеграм просит подождать {wait_time} сек...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            errors += 1
            if errors > 3:
                await message.reply("❌ Слишком много ошибок. Давай остановимся.")
                break
            continue
    
    # Итоговое сообщение
    if created > 0:
        await human_delay("long")
        await message.reply(
            f"✅ **Готово!**\n"
            f"Создано каналов: {created}\n"
            f"Ошибок: {errors}\n\n"
            f"Что делаем дальше?"
        )
    else:
        await message.reply("❌ Не удалось создать ни одного канала :(")
    
    user_state[user_id] = "main_menu"

# Функция для получения клиента пользователя
async def get_user_client(user_id):
    """Получает или создает клиент пользователя"""
    if user_id in user_clients and user_clients[user_id].is_connected:
        return user_clients[user_id]
    
    session_file = f"{SESSION_NAME}_{user_id}.session"
    if not os.path.exists(session_file):
        return None
    
    client = Client(
        f"{SESSION_NAME}_{user_id}",
        api_id=user_data.get(user_id, {}).get("api_id", API_ID),
        api_hash=user_data.get(user_id, {}).get("api_hash", API_HASH)
    )
    
    await client.start()
    user_clients[user_id] = client
    return client

# Основная функция с полной маскировкой
async def main():
    try:
        # Маскируем бота под обычное приложение
        bot = Client(
            "bot_session",
            bot_token=BOT_TOKEN,
            api_id=6,
            api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
            device_model="Desktop PC",
            system_version="Windows 10",
            app_version="1.0.0",
            lang_code="ru"
        )
        
        # Регистрируем обработчики с человеческими именами
        @bot.on_message(filters.command("start"))
        async def on_start(client, message):
            await start_command(client, message)
        
        @bot.on_message(filters.text & filters.private)
        async def on_message(client, message):
            user_id = message.from_user.id
            
            # Игнорируем служебные сообщения
            if message.text.startswith('/'):
                return
            
            # Человеческая задержка перед ответом
            await human_delay("typing")
            await simulate_typing(client, message.chat.id)
            
            # Определяем состояние
            state = user_state.get(user_id, "main_menu")
            
            if state == "main_menu":
                await handle_main_menu(client, message)
            elif state.startswith("channel_"):
                await handle_channel_creation(client, message)
            else:
                # Если состояние неизвестно - возвращаем в меню
                response = get_human_phrase('thinking')
                await message.reply(response)
                await asyncio.sleep(1)
                await message.reply("Давай начнем сначала. Выбери действие:", reply_markup=main_keyboard)
                user_state[user_id] = "main_menu"
        
        logger.info("✅ Бот запущен и замаскирован под человека")
        logger.info(f"🤖 Имя бота: {bot.me.first_name if bot.me else 'Unknown'}")
        
        # Запускаем бота
        await bot.start()
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
    finally:
        # Очищаем ресурсы
        for client in user_clients.values():
            try:
                await client.stop()
            except:
                pass
        
        if 'bot' in locals():
            await bot.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
