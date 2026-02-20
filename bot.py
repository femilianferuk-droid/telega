import asyncio
import re
import os
import sys
import logging
import random
import json
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton
from pyrogram.errors import (
    FloodWait,
    PhoneNumberInvalid, PhoneCodeInvalid, PasswordHashInvalid,
    SessionPasswordNeeded, ApiIdInvalid
)
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Конфигурация с вашими API данными
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = 32480523  # Ваш API ID
API_HASH = "147839735c9fa4e83451209e9b55cfc5"  # Ваш API Hash
SESSION_NAME = "account_session"

# Проверяем токен
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в .env")
    print("Добавьте строку: BOT_TOKEN=ваш_токен_от_botfather")
    sys.exit(1)

# Глобальные переменные
user_state = {}  # Состояние пользователя
user_data = {}   # Данные пользователя
accounts = {}    # Менеджер аккаунтов {user_id: {account_name: client}}
active_clients = {}  # Активные клиенты

# Клавиатуры
main_keyboard = ReplyKeyboardMarkup(
    [
        ["📢 Создать канал", "👥 Создать группу"],
        ["👤 Менеджер аккаунтов", "❓ Помощь"]
    ],
    resize_keyboard=True
)

accounts_keyboard = ReplyKeyboardMarkup(
    [
        ["➕ Добавить аккаунт", "📋 Список аккаунтов"],
        ["🔑 Выбрать аккаунт", "❌ Удалить аккаунт"],
        ["🔙 Назад"]
    ],
    resize_keyboard=True
)

yes_no_keyboard = ReplyKeyboardMarkup(
    [
        ["Да", "Нет"],
        ["🔙 Назад"]
    ],
    resize_keyboard=True
)

# Функция для сохранения аккаунтов
def save_accounts(user_id):
    """Сохраняет аккаунты пользователя в файл"""
    if user_id in accounts:
        filename = f"accounts_{user_id}.json"
        data = {}
        for acc_name, client in accounts[user_id].items():
            if client and hasattr(client, 'storage'):
                try:
                    # Пытаемся сохранить сессию
                    data[acc_name] = {
                        "name": acc_name,
                        "session_file": f"{SESSION_NAME}_{user_id}_{acc_name}.session"
                    }
                except:
                    data[acc_name] = {"name": acc_name, "session_file": None}
            else:
                data[acc_name] = {"name": acc_name, "session_file": None}
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def load_accounts(user_id):
    """Загружает аккаунты пользователя из файла"""
    filename = f"accounts_{user_id}.json"
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if user_id not in accounts:
                accounts[user_id] = {}
            
            for acc_name, acc_data in data.items():
                session_file = acc_data.get("session_file")
                if session_file and os.path.exists(session_file):
                    # Будет загружено при необходимости
                    accounts[user_id][acc_name] = None
                else:
                    accounts[user_id][acc_name] = None

# Функция для получения клиента аккаунта
async def get_account_client(user_id, account_name):
    """Получает или создает клиент для аккаунта"""
    if user_id in accounts and account_name in accounts[user_id]:
        client = accounts[user_id][account_name]
        if client and client.is_connected:
            return client
        
        # Создаем нового клиента
        session_file = f"{SESSION_NAME}_{user_id}_{account_name}"
        client = Client(
            session_file,
            api_id=API_ID,
            api_hash=API_HASH,
            device_model=f"PC_{random.randint(1000, 9999)}",
            system_version="Windows 10",
            app_version="1.0.0",
            lang_code="ru"
        )
        
        try:
            await client.start()
            accounts[user_id][account_name] = client
            return client
        except Exception as e:
            logger.error(f"Ошибка загрузки клиента: {e}")
            return None
    
    return None

# Обработчик команды /start
async def start_command(client, message):
    user_id = message.from_user.id
    
    # Загружаем сохраненные аккаунты
    load_accounts(user_id)
    
    await message.reply(
        "👋 **Привет!**\n\n"
        "Я помогу создавать каналы и группы.\n"
        "Используй менеджер аккаунтов для добавления Telegram аккаунтов.",
        reply_markup=main_keyboard
    )
    user_state[user_id] = "main_menu"

# Обработчик главного меню
async def handle_main_menu(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "📢 Создать канал":
        # Проверяем наличие аккаунтов
        if user_id not in accounts or not accounts[user_id]:
            await message.reply("❌ Сначала добавьте аккаунт в менеджере аккаунтов")
            return
        
        # Показываем список аккаунтов для выбора
        acc_list = "Выберите аккаунт для создания каналов:\n\n"
        for i, acc_name in enumerate(accounts[user_id].keys(), 1):
            status = "✅" if accounts[user_id][acc_name] else "❌"
            acc_list += f"{i}. {status} {acc_name}\n"
        
        await message.reply(acc_list)
        user_state[user_id] = "channel_select_account"
    
    elif text == "👥 Создать группу":
        if user_id not in accounts or not accounts[user_id]:
            await message.reply("❌ Сначала добавьте аккаунт в менеджере аккаунтов")
            return
        
        acc_list = "Выберите аккаунт для создания групп:\n\n"
        for i, acc_name in enumerate(accounts[user_id].keys(), 1):
            status = "✅" if accounts[user_id][acc_name] else "❌"
            acc_list += f"{i}. {status} {acc_name}\n"
        
        await message.reply(acc_list)
        user_state[user_id] = "group_select_account"
    
    elif text == "👤 Менеджер аккаунтов":
        user_state[user_id] = "accounts_menu"
        await message.reply(
            "👤 **Менеджер аккаунтов**\n\n"
            "Максимум 5 аккаунтов",
            reply_markup=accounts_keyboard
        )
    
    elif text == "❓ Помощь":
        await message.reply(
            "❓ **Помощь**\n\n"
            "1. Добавьте аккаунты в менеджере\n"
            "2. Авторизуйте их\n"
            "3. Выбирайте аккаунт для создания\n"
            "4. Указывайте параметры\n\n"
            "Максимум 20 каналов/групп за раз"
        )

# Обработчик менеджера аккаунтов
async def handle_accounts(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "➕ Добавить аккаунт":
        if user_id in accounts and len(accounts[user_id]) >= 5:
            await message.reply("❌ Нельзя добавить больше 5 аккаунтов")
            return
        
        user_state[user_id] = "add_account_name"
        await message.reply(
            "Введите название для аккаунта (например: Основной, Рабочий):",
            reply_markup=yes_no_keyboard
        )
    
    elif text == "📋 Список аккаунтов":
        if user_id not in accounts or not accounts[user_id]:
            await message.reply("📭 Нет добавленных аккаунтов")
        else:
            account_list = "📋 **Ваши аккаунты:**\n\n"
            for i, (acc_name, acc_client) in enumerate(accounts[user_id].items(), 1):
                if acc_client and acc_client.is_connected:
                    try:
                        me = await acc_client.get_me()
                        phone = me.phone_number if me else "неизвестно"
                        status = f"✅ {phone}"
                    except:
                        status = "✅ активен"
                else:
                    status = "❌ не авторизован"
                account_list += f"{i}. **{acc_name}** - {status}\n"
            await message.reply(account_list)
    
    elif text == "🔑 Выбрать аккаунт":
        if user_id not in accounts or not accounts[user_id]:
            await message.reply("❌ Сначала добавьте аккаунт")
        else:
            acc_list = "Выберите аккаунт:\n\n"
            for i, acc_name in enumerate(accounts[user_id].keys(), 1):
                status = "✅" if accounts[user_id][acc_name] else "❌"
                acc_list += f"{i}. {status} {acc_name}\n"
            await message.reply(acc_list)
            user_state[user_id] = "select_account"
    
    elif text == "❌ Удалить аккаунт":
        if user_id not in accounts or not accounts[user_id]:
            await message.reply("📭 Нет аккаунтов для удаления")
        else:
            acc_list = "Выберите аккаунт для удаления:\n\n"
            for i, acc_name in enumerate(accounts[user_id].keys(), 1):
                acc_list += f"{i}. {acc_name}\n"
            await message.reply(acc_list)
            user_state[user_id] = "delete_account"
    
    elif text == "🔙 Назад":
        user_state[user_id] = "main_menu"
        await message.reply("Главное меню:", reply_markup=main_keyboard)

# Обработчик добавления аккаунта
async def handle_add_account(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if user_state.get(user_id) == "add_account_name":
        if text == "🔙 Назад":
            user_state[user_id] = "accounts_menu"
            await message.reply("Менеджер аккаунтов:", reply_markup=accounts_keyboard)
            return
        
        account_name = text
        if user_id not in accounts:
            accounts[user_id] = {}
        
        if account_name in accounts[user_id]:
            await message.reply("❌ Аккаунт с таким именем уже существует")
            return
        
        accounts[user_id][account_name] = None
        save_accounts(user_id)
        
        # Создаем временный клиент для авторизации
        session_file = f"{SESSION_NAME}_{user_id}_{account_name}"
        temp_client = Client(
            session_file,
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True
        )
        
        try:
            await temp_client.connect()
            user_data[user_id] = {
                "account_name": account_name,
                "temp_client": temp_client
            }
            
            await message.reply(
                f"✅ Аккаунт '{account_name}' создан\n\n"
                "📱 Введите номер телефона (например: +79123456789):"
            )
            user_state[user_id] = "auth_phone"
            
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
            await temp_client.disconnect()
    
    elif user_state.get(user_id) == "auth_phone":
        phone = text
        temp_client = user_data[user_id]["temp_client"]
        
        try:
            sent_code = await temp_client.send_code(phone)
            user_data[user_id]["phone"] = phone
            user_data[user_id]["phone_code_hash"] = sent_code.phone_code_hash
            
            await message.reply("📱 Введите код из Telegram:")
            user_state[user_id] = "auth_code"
            
        except PhoneNumberInvalid:
            await message.reply("❌ Неверный номер телефона")
        except FloodWait as e:
            await message.reply(f"⏳ Подождите {e.value} секунд")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
    
    elif user_state.get(user_id) == "auth_code":
        temp_client = user_data[user_id]["temp_client"]
        
        try:
            await temp_client.sign_in(
                user_data[user_id]["phone"],
                user_data[user_id]["phone_code_hash"],
                text
            )
            
            # Сохраняем клиент
            account_name = user_data[user_id]["account_name"]
            accounts[user_id][account_name] = temp_client
            save_accounts(user_id)
            
            await message.reply(
                f"✅ Аккаунт '{account_name}' успешно авторизован!",
                reply_markup=main_keyboard
            )
            user_state[user_id] = "main_menu"
            
        except SessionPasswordNeeded:
            user_state[user_id] = "auth_2fa"
            await message.reply("🔐 Введите пароль двухфакторной аутентификации:")
        except PhoneCodeInvalid:
            await message.reply("❌ Неверный код")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
    
    elif user_state.get(user_id) == "auth_2fa":
        temp_client = user_data[user_id]["temp_client"]
        
        try:
            await temp_client.check_password(text)
            
            account_name = user_data[user_id]["account_name"]
            accounts[user_id][account_name] = temp_client
            save_accounts(user_id)
            
            await message.reply(
                f"✅ Аккаунт '{account_name}' успешно авторизован!",
                reply_markup=main_keyboard
            )
            user_state[user_id] = "main_menu"
            
        except PasswordHashInvalid:
            await message.reply("❌ Неверный пароль")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")

# Обработчик создания каналов
async def handle_channel_creation(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if user_state.get(user_id) == "channel_select_account":
        if text == "🔙 Назад":
            user_state[user_id] = "main_menu"
            await message.reply("Главное меню:", reply_markup=main_keyboard)
            return
        
        try:
            acc_index = int(text) - 1
            account_names = list(accounts[user_id].keys())
            
            if 0 <= acc_index < len(account_names):
                account_name = account_names[acc_index]
                
                # Получаем клиент аккаунта
                user_client = await get_account_client(user_id, account_name)
                if not user_client:
                    await message.reply("❌ Не удалось подключиться к аккаунту")
                    return
                
                user_data[user_id] = {
                    "selected_account": account_name,
                    "client": user_client
                }
                user_state[user_id] = "channel_name"
                
                await message.reply(
                    "📢 Введите название для каналов (будет добавлен номер):",
                    reply_markup=yes_no_keyboard
                )
            else:
                await message.reply("❌ Неверный номер аккаунта")
        except ValueError:
            await message.reply("❌ Введите номер аккаунта")
    
    elif user_state.get(user_id) == "channel_name":
        if text == "🔙 Назад":
            user_state[user_id] = "channel_select_account"
            await message.reply("Выберите аккаунт:")
            return
        
        user_data[user_id]["channel_base_name"] = text
        user_state[user_id] = "channel_public"
        await message.reply("Сделать каналы публичными?", reply_markup=yes_no_keyboard)
    
    elif user_state.get(user_id) == "channel_public":
        if text == "🔙 Назад":
            user_state[user_id] = "channel_name"
            await message.reply("Введите название каналов:")
            return
        
        if text == "Да":
            user_data[user_id]["channel_public"] = True
            user_state[user_id] = "channel_username"
            await message.reply(
                "Введите базовый username (например: news_channel):",
                reply_markup=yes_no_keyboard
            )
        else:
            user_data[user_id]["channel_public"] = False
            user_state[user_id] = "channel_count"
            await message.reply("Сколько каналов создать? (1-20):")
    
    elif user_state.get(user_id) == "channel_username":
        if text == "🔙 Назад":
            user_state[user_id] = "channel_public"
            await message.reply("Сделать каналы публичными?", reply_markup=yes_no_keyboard)
            return
        
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', text):
            user_data[user_id]["channel_base_username"] = text
            user_state[user_id] = "channel_count"
            await message.reply("Сколько каналов создать? (1-20):")
        else:
            await message.reply("❌ Неверный формат username")
    
    elif user_state.get(user_id) == "channel_count":
        if text == "🔙 Назад":
            if user_data[user_id].get("channel_public"):
                user_state[user_id] = "channel_username"
                await message.reply("Введите базовый username:")
            else:
                user_state[user_id] = "channel_public"
                await message.reply("Сделать каналы публичными?", reply_markup=yes_no_keyboard)
            return
        
        try:
            count = int(text)
            if 1 <= count <= 20:
                user_data[user_id]["channel_count"] = count
                user_state[user_id] = "channel_archive"
                await message.reply("Архивировать каналы после создания?", reply_markup=yes_no_keyboard)
            else:
                await message.reply("❌ Введите число от 1 до 20")
        except ValueError:
            await message.reply("❌ Введите число")
    
    elif user_state.get(user_id) == "channel_archive":
        if text == "🔙 Назад":
            user_state[user_id] = "channel_count"
            await message.reply("Сколько каналов создать?")
            return
        
        archive = (text == "Да")
        user_client = user_data[user_id]["client"]
        account_name = user_data[user_id]["selected_account"]
        
        await message.reply(f"🚀 Начинаю создание каналов через аккаунт {account_name}...")
        
        created = 0
        errors = 0
        
        for i in range(1, user_data[user_id]["channel_count"] + 1):
            try:
                # Задержка между созданиями
                if i > 1:
                    delay = random.uniform(10, 15)
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
                    description=f"Создано {datetime.now().strftime('%d.%m.%Y')}",
                    username=username
                )
                
                # Архивируем если нужно
                if archive:
                    try:
                        await user_client.archive_chats(channel.id)
                    except:
                        pass
                
                created += 1
                
                username_str = f"@{username}" if username else "приватный"
                await message.reply(f"✅ Канал {i}: {channel_title} - {username_str}")
                
            except FloodWait as e:
                await message.reply(f"⏳ Flood wait {e.value} сек")
                await asyncio.sleep(e.value)
            except Exception as e:
                errors += 1
                await message.reply(f"❌ Ошибка: {str(e)}")
        
        await message.reply(
            f"✅ **Готово!**\n"
            f"Создано: {created}\n"
            f"Ошибок: {errors}",
            reply_markup=main_keyboard
        )
        user_state[user_id] = "main_menu"

# Основная функция
async def main():
    try:
        # Создаем клиента бота
        bot = Client(
            "bot_session",
            bot_token=BOT_TOKEN,
            api_id=API_ID,
            api_hash=API_HASH
        )
        
        # Регистрируем обработчики
        @bot.on_message(filters.command("start"))
        async def start_handler(client, message):
            await start_command(client, message)
        
        @bot.on_message(filters.text & filters.private)
        async def message_handler(client, message):
            user_id = message.from_user.id
            text = message.text
            
            # Инициализация для новых пользователей
            if user_id not in user_state:
                user_state[user_id] = "main_menu"
                await start_command(client, message)
                return
            
            state = user_state.get(user_id)
            
            try:
                # Маршрутизация по состояниям
                if state == "main_menu":
                    await handle_main_menu(client, message)
                
                elif state == "accounts_menu":
                    await handle_accounts(client, message)
                
                elif state in ["add_account_name", "auth_phone", "auth_code", "auth_2fa"]:
                    await handle_add_account(client, message)
                
                elif state in ["select_account", "delete_account"]:
                    # Обработка выбора/удаления аккаунта
                    if text == "🔙 Назад":
                        user_state[user_id] = "accounts_menu"
                        await message.reply("Менеджер аккаунтов:", reply_markup=accounts_keyboard)
                    else:
                        try:
                            acc_index = int(text) - 1
                            account_names = list(accounts[user_id].keys())
                            
                            if 0 <= acc_index < len(account_names):
                                account_name = account_names[acc_index]
                                
                                if state == "select_account":
                                    await message.reply(f"✅ Выбран аккаунт: {account_name}")
                                else:  # delete_account
                                    # Удаляем сессию
                                    session_file = f"{SESSION_NAME}_{user_id}_{account_name}.session"
                                    if os.path.exists(session_file):
                                        os.remove(session_file)
                                    
                                    if accounts[user_id][account_name]:
                                        await accounts[user_id][account_name].stop()
                                    
                                    del accounts[user_id][account_name]
                                    save_accounts(user_id)
                                    await message.reply(f"✅ Аккаунт {account_name} удален")
                                
                                user_state[user_id] = "accounts_menu"
                                await message.reply("Менеджер аккаунтов:", reply_markup=accounts_keyboard)
                            else:
                                await message.reply("❌ Неверный номер")
                        except ValueError:
                            await message.reply("❌ Введите номер")
                
                elif state.startswith("channel_"):
                    await handle_channel_creation(client, message)
                
                else:
                    user_state[user_id] = "main_menu"
                    await message.reply("Главное меню:", reply_markup=main_keyboard)
                    
            except Exception as e:
                logger.error(f"Ошибка: {e}", exc_info=True)
                await message.reply(f"❌ Ошибка: {str(e)}")
                user_state[user_id] = "main_menu"
        
        logger.info("✅ Бот запущен")
        logger.info(f"🤖 Бот @{bot.me.username} активен")
        
        await bot.start()
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
    finally:
        # Очищаем ресурсы
        for user_accs in accounts.values():
            for client in user_accs.values():
                if client:
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
