import asyncio
import re
import os
import sys
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from pyrogram.errors import (
    UsernameNotOccupied, UsernameInvalid, FloodWait,
    PhoneNumberInvalid, PhoneCodeInvalid, PasswordHashInvalid,
    SessionPasswordNeeded, ApiIdInvalid, AccessTokenInvalid
)
from pyrogram.enums import ChatType
import time
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "user_session"

# Проверяем наличие токена при запуске
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
    print("Создайте файл .env и добавьте строку: BOT_TOKEN=ваш_токен")
    print("Пример: BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
    sys.exit(1)

# Глобальные переменные для хранения состояния пользователя
user_state = {}
user_data = {}

# Клавиатуры
main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📢 Создание каналов")],
        [KeyboardButton("👥 Создание групп")]
    ],
    resize_keyboard=True
)

yes_no_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Да"), KeyboardButton("Нет")]
    ],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("❌ Отмена")]
    ],
    resize_keyboard=True
)

# Функция для проверки отмены
async def check_cancel(message, text=None):
    if text and text.lower() in ['/cancel', 'отмена', '❌ отмена']:
        await message.reply("❌ Операция отменена. Возврат в главное меню.", reply_markup=main_keyboard)
        user_state[message.from_user.id] = "main_menu"
        return True
    return False

# Обработчик команды /start
async def start_command(client, message):
    user_id = message.from_user.id
    
    # Проверяем, существует ли сессия пользователя
    session_file = f"{SESSION_NAME}_{user_id}.session"
    if os.path.exists(session_file):
        user_state[user_id] = "main_menu"
        await message.reply(
            "✅ Сессия найдена! Добро пожаловать в главное меню.",
            reply_markup=main_keyboard
        )
    else:
        # Проверяем, есть ли API данные в переменных окружения
        if API_ID and API_HASH:
            try:
                user_data[user_id] = {
                    "api_id": int(API_ID),
                    "api_hash": API_HASH
                }
                user_state[user_id] = "waiting_phone"
                await message.reply(
                    "📱 API данные загружены из окружения.\n"
                    "Введите номер телефона (в международном формате, например: +79123456789):",
                    reply_markup=cancel_keyboard
                )
            except ValueError:
                user_state[user_id] = "waiting_api_id"
                await message.reply(
                    "❌ API_ID в файле .env должен быть числом!\n\n"
                    "🔐 **Процесс авторизации**\n\n"
                    "Пожалуйста, введите ваш **api_id** вручную:\n"
                    "(Получить можно на my.telegram.org/apps)",
                    reply_markup=cancel_keyboard
                )
        else:
            user_state[user_id] = "waiting_api_id"
            await message.reply(
                "🔐 **Процесс авторизации**\n\n"
                "Пожалуйста, введите ваш **api_id**:\n"
                "(Получить можно на my.telegram.org/apps)",
                reply_markup=cancel_keyboard
            )

# Обработчик основного меню
async def handle_main_menu(client, message):
    user_id = message.from_user.id
    
    if message.text == "📢 Создание каналов":
        user_state[user_id] = "channel_name"
        await message.reply(
            "📢 **Создание каналов**\n\n"
            "Введите название для каналов (будет добавлен номер):",
            reply_markup=cancel_keyboard
        )
    
    elif message.text == "👥 Создание групп":
        user_state[user_id] = "group_name"
        await message.reply(
            "👥 **Создание групп**\n\n"
            "Введите название для групп (будет добавлен номер):",
            reply_markup=cancel_keyboard
        )
    else:
        await message.reply("Пожалуйста, используйте кнопки меню.", reply_markup=main_keyboard)

# Обработчик авторизации
async def handle_auth(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if await check_cancel(message, text):
        return
    
    if user_state.get(user_id) == "waiting_api_id":
        if text.isdigit():
            user_data[user_id] = {"api_id": int(text)}
            user_state[user_id] = "waiting_api_hash"
            await message.reply("✅ API ID принят. Теперь введите **api_hash**:")
        else:
            await message.reply("❌ API ID должен быть числом. Попробуйте снова:")
    
    elif user_state.get(user_id) == "waiting_api_hash":
        user_data[user_id]["api_hash"] = text
        user_state[user_id] = "waiting_phone"
        await message.reply("✅ API Hash принят. Введите номер телефона (в международном формате):")
    
    elif user_state.get(user_id) == "waiting_phone":
        user_data[user_id]["phone"] = text
        user_state[user_id] = "waiting_code"
        
        # Создаем временный клиент для авторизации
        temp_client = Client(
            f"{SESSION_NAME}_{user_id}",
            api_id=user_data[user_id]["api_id"],
            api_hash=user_data[user_id]["api_hash"],
            in_memory=True
        )
        
        try:
            await temp_client.connect()
            
            sent_code = await temp_client.send_code(user_data[user_id]["phone"])
            user_data[user_id]["phone_code_hash"] = sent_code.phone_code_hash
            user_data[user_id]["temp_client"] = temp_client
            
            await message.reply("📱 Код подтверждения отправлен. Введите код из SMS/Telegram:")
            
        except PhoneNumberInvalid:
            await message.reply("❌ Неверный номер телефона. Попробуйте снова:")
            user_state[user_id] = "waiting_phone"
            await temp_client.disconnect()
        except ApiIdInvalid:
            await message.reply("❌ Неверный API ID или API Hash. Попробуйте снова:")
            user_state[user_id] = "waiting_api_id"
            await temp_client.disconnect()
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
            user_state[user_id] = "waiting_phone"
            await temp_client.disconnect()
    
    elif user_state.get(user_id) == "waiting_code":
        temp_client = user_data[user_id]["temp_client"]
        
        try:
            await temp_client.sign_in(
                user_data[user_id]["phone"],
                user_data[user_id]["phone_code_hash"],
                text
            )
            
            # Сохраняем сессию
            await temp_client.storage.save()
            await temp_client.disconnect()
            
            user_state[user_id] = "main_menu"
            await message.reply(
                "✅ Авторизация успешна! Добро пожаловать в главное меню.",
                reply_markup=main_keyboard
            )
            
        except SessionPasswordNeeded:
            user_state[user_id] = "waiting_2fa"
            await message.reply("🔐 Требуется двухфакторная аутентификация. Введите пароль:")
        except PhoneCodeInvalid:
            await message.reply("❌ Неверный код. Попробуйте снова:")
        except FloodWait as e:
            await message.reply(f"❌ Слишком много попыток. Подождите {e.value} секунд")
            await asyncio.sleep(e.value)
            user_state[user_id] = "waiting_code"
    
    elif user_state.get(user_id) == "waiting_2fa":
        temp_client = user_data[user_id]["temp_client"]
        
        try:
            await temp_client.check_password(text)
            await temp_client.storage.save()
            await temp_client.disconnect()
            
            user_state[user_id] = "main_menu"
            await message.reply(
                "✅ Авторизация успешна! Добро пожаловать в главное меню.",
                reply_markup=main_keyboard
            )
        except PasswordHashInvalid:
            await message.reply("❌ Неверный пароль. Попробуйте снова:")
        except FloodWait as e:
            await message.reply(f"❌ Слишком много попыток. Подождите {e.value} секунд")
            await asyncio.sleep(e.value)

# Обработчик создания каналов
async def handle_channel_creation(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if await check_cancel(message, text):
        return
    
    state = user_state.get(user_id)
    
    if state == "channel_name":
        user_data[user_id] = {"channel_base_name": text}
        user_state[user_id] = "channel_public"
        await message.reply(
            "Сделать каналы публичными?",
            reply_markup=yes_no_keyboard
        )
    
    elif state == "channel_public":
        if text == "Да":
            user_data[user_id]["channel_public"] = True
            user_state[user_id] = "channel_username"
            await message.reply(
                "Введите базовый username для каналов (будет добавлен номер):\n"
                "Пример: great_news",
                reply_markup=cancel_keyboard
            )
        elif text == "Нет":
            user_data[user_id]["channel_public"] = False
            user_state[user_id] = "channel_count"
            await message.reply(
                "Введите количество каналов для создания (1-100):",
                reply_markup=cancel_keyboard
            )
        else:
            await message.reply("Пожалуйста, выберите Да или Нет", reply_markup=yes_no_keyboard)
    
    elif state == "channel_username":
        # Проверяем валидность username
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', text):
            user_data[user_id]["channel_base_username"] = text
            user_state[user_id] = "channel_count"
            await message.reply(
                "Введите количество каналов для создания (1-100):",
                reply_markup=cancel_keyboard
            )
        else:
            await message.reply(
                "❌ Некорректный username. Он должен:\n"
                "• Начинаться с буквы\n"
                "• Содержать только буквы, цифры и _\n"
                "• Быть длиной 4-30 символов\n"
                "Попробуйте снова:"
            )
    
    elif state == "channel_count":
        try:
            count = int(text)
            if 1 <= count <= 100:
                user_data[user_id]["channel_count"] = count
                user_state[user_id] = "channel_archive"
                await message.reply(
                    "Добавлять созданные каналы в архив?",
                    reply_markup=yes_no_keyboard
                )
            else:
                await message.reply("❌ Введите число от 1 до 100:")
        except ValueError:
            await message.reply("❌ Введите корректное число:")
    
    elif state == "channel_archive":
        if text in ["Да", "Нет"]:
            archive = (text == "Да")
            
            # Проверяем наличие сессии
            session_file = f"{SESSION_NAME}_{user_id}.session"
            if not os.path.exists(session_file):
                await message.reply("❌ Сессия не найдена. Начните заново с /start")
                user_state[user_id] = "main_menu"
                return
            
            # Создаем клиент с сохраненной сессией
            user_client = Client(
                f"{SESSION_NAME}_{user_id}",
                api_id=user_data[user_id].get("api_id", API_ID),
                api_hash=user_data[user_id].get("api_hash", API_HASH)
            )
            
            try:
                await user_client.start()
                
                await message.reply(
                    "🚀 Начинаю создание каналов...",
                    reply_markup=main_keyboard
                )
                
                # Создаем каналы
                for i in range(1, user_data[user_id]["channel_count"] + 1):
                    try:
                        # Формируем название и username
                        channel_title = f"{user_data[user_id]['channel_base_name']} {i}"
                        
                        if user_data[user_id].get("channel_public"):
                            username = f"{user_data[user_id]['channel_base_username']}{i if i > 1 else ''}"
                        else:
                            username = None
                        
                        # Создаем канал
                        channel = await user_client.create_channel(
                            title=channel_title,
                            description=f"Канал {channel_title}",
                            username=username
                        )
                        
                        # Архивируем если нужно
                        if archive:
                            try:
                                await user_client.archive_chats(channel.id)
                            except Exception as e:
                                await message.reply(f"⚠️ Не удалось архивировать канал {i}: {str(e)}")
                        
                        # Выводим информацию
                        username_str = f"@{username}" if username else "приватный"
                        await message.reply(
                            f"✅ **Создан канал {i}:**\n"
                            f"📌 Название: {channel_title}\n"
                            f"🔗 Ссылка: {username_str}"
                        )
                        
                        # Задержка 10 секунд между созданиями
                        if i < user_data[user_id]["channel_count"]:
                            await asyncio.sleep(10)
                            
                    except FloodWait as e:
                        wait_time = e.value
                        await message.reply(f"⏳ Flood wait! Ожидание {wait_time} секунд...")
                        await asyncio.sleep(wait_time)
                    except Exception as e:
                        await message.reply(f"❌ Ошибка при создании канала {i}: {str(e)}")
                        continue
                
                await user_client.stop()
                await message.reply("✅ Создание каналов завершено!", reply_markup=main_keyboard)
                
            except Exception as e:
                await message.reply(f"❌ Ошибка при подключении: {str(e)}")
                await user_client.stop()
            
            user_state[user_id] = "main_menu"
        else:
            await message.reply("Пожалуйста, выберите Да или Нет", reply_markup=yes_no_keyboard)

# Обработчик создания групп
async def handle_group_creation(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if await check_cancel(message, text):
        return
    
    state = user_state.get(user_id)
    
    if state == "group_name":
        user_data[user_id] = {"group_base_name": text}
        user_state[user_id] = "group_public"
        await message.reply(
            "Сделать группы публичными?",
            reply_markup=yes_no_keyboard
        )
    
    elif state == "group_public":
        if text == "Да":
            user_data[user_id]["group_public"] = True
            user_state[user_id] = "group_username"
            await message.reply(
                "Введите базовый username для групп (будет добавлен номер):",
                reply_markup=cancel_keyboard
            )
        elif text == "Нет":
            user_data[user_id]["group_public"] = False
            user_state[user_id] = "group_count"
            await message.reply(
                "Введите количество групп для создания (1-100):",
                reply_markup=cancel_keyboard
            )
        else:
            await message.reply("Пожалуйста, выберите Да или Нет", reply_markup=yes_no_keyboard)
    
    elif state == "group_username":
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', text):
            user_data[user_id]["group_base_username"] = text
            user_state[user_id] = "group_count"
            await message.reply(
                "Введите количество групп для создания (1-100):",
                reply_markup=cancel_keyboard
            )
        else:
            await message.reply("❌ Некорректный username. Попробуйте снова:")
    
    elif state == "group_count":
        try:
            count = int(text)
            if 1 <= count <= 100:
                user_data[user_id]["group_count"] = count
                user_state[user_id] = "group_message"
                await message.reply(
                    "Отправить приветственное сообщение в группы?",
                    reply_markup=yes_no_keyboard
                )
            else:
                await message.reply("❌ Введите число от 1 до 100:")
        except ValueError:
            await message.reply("❌ Введите корректное число:")
    
    elif state == "group_message":
        if text == "Да":
            user_data[user_id]["group_send_message"] = True
            user_state[user_id] = "group_message_text"
            await message.reply(
                "Введите текст приветственного сообщения:",
                reply_markup=cancel_keyboard
            )
        elif text == "Нет":
            user_data[user_id]["group_send_message"] = False
            user_state[user_id] = "group_archive"
            await message.reply(
                "Закидывать группы в архив сразу после создания?",
                reply_markup=yes_no_keyboard
            )
        else:
            await message.reply("Пожалуйста, выберите Да или Нет", reply_markup=yes_no_keyboard)
    
    elif state == "group_message_text":
        user_data[user_id]["group_message_text"] = text
        user_state[user_id] = "group_archive"
        await message.reply(
            "Закидывать группы в архив сразу после создания?",
            reply_markup=yes_no_keyboard
        )
    
    elif state == "group_archive":
        if text in ["Да", "Нет"]:
            archive = (text == "Да")
            
            # Проверяем наличие сессии
            session_file = f"{SESSION_NAME}_{user_id}.session"
            if not os.path.exists(session_file):
                await message.reply("❌ Сессия не найдена. Начните заново с /start")
                user_state[user_id] = "main_menu"
                return
            
            # Создаем клиент с сохраненной сессией
            user_client = Client(
                f"{SESSION_NAME}_{user_id}",
                api_id=user_data[user_id].get("api_id", API_ID),
                api_hash=user_data[user_id].get("api_hash", API_HASH)
            )
            
            try:
                await user_client.start()
                
                await message.reply(
                    "🚀 Начинаю создание групп...",
                    reply_markup=main_keyboard
                )
                
                # Создаем группы
                for i in range(1, user_data[user_id]["group_count"] + 1):
                    try:
                        # Формируем название и username
                        group_title = f"{user_data[user_id]['group_base_name']} {i}"
                        
                        if user_data[user_id].get("group_public"):
                            username = f"{user_data[user_id]['group_base_username']}{i if i > 1 else ''}"
                        else:
                            username = None
                        
                        # Создаем супергруппу
                        group = await user_client.create_supergroup(
                            title=group_title,
                            description=f"Группа {group_title}",
                            username=username
                        )
                        
                        # Отправляем сообщение если нужно
                        if user_data[user_id].get("group_send_message"):
                            try:
                                await user_client.send_message(
                                    group.id,
                                    user_data[user_id].get("group_message_text", "Добро пожаловать!")
                                )
                            except Exception as e:
                                await message.reply(f"⚠️ Не удалось отправить сообщение в группу {i}: {str(e)}")
                        
                        # Архивируем если нужно
                        if archive:
                            try:
                                await user_client.archive_chats(group.id)
                            except Exception as e:
                                await message.reply(f"⚠️ Не удалось архивировать группу {i}: {str(e)}")
                        
                        # Выводим информацию
                        username_str = f"@{username}" if username else "приватная"
                        await message.reply(
                            f"✅ **Создана группа {i}:**\n"
                            f"📌 Название: {group_title}\n"
                            f"🔗 Ссылка: {username_str}"
                        )
                        
                        # Задержка 10 секунд между созданиями
                        if i < user_data[user_id]["group_count"]:
                            await asyncio.sleep(10)
                            
                    except FloodWait as e:
                        wait_time = e.value
                        await message.reply(f"⏳ Flood wait! Ожидание {wait_time} секунд...")
                        await asyncio.sleep(wait_time)
                    except Exception as e:
                        await message.reply(f"❌ Ошибка при создании группы {i}: {str(e)}")
                        continue
                
                await user_client.stop()
                await message.reply("✅ Создание групп завершено!", reply_markup=main_keyboard)
                
            except Exception as e:
                await message.reply(f"❌ Ошибка при подключении: {str(e)}")
                await user_client.stop()
            
            user_state[user_id] = "main_menu"
        else:
            await message.reply("Пожалуйста, выберите Да или Нет", reply_markup=yes_no_keyboard)

# Главная функция
async def main():
    try:
        # Создаем клиента бота
        bot = Client(
            "bot_session",
            bot_token=BOT_TOKEN,
            api_id=6,
            api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e"
        )
        
        # Регистрируем обработчики
        @bot.on_message(filters.command("start"))
        async def start_handler(client, message):
            await start_command(client, message)
        
        @bot.on_message(filters.text & filters.private)
        async def message_handler(client, message):
            user_id = message.from_user.id
            
            if user_id not in user_state:
                user_state[user_id] = "main_menu"
                await start_command(client, message)
                return
            
            state = user_state.get(user_id)
            
            try:
                if state == "main_menu":
                    await handle_main_menu(client, message)
                elif state in ["waiting_api_id", "waiting_api_hash", "waiting_phone", "waiting_code", "waiting_2fa"]:
                    await handle_auth(client, message)
                elif state.startswith("channel_"):
                    await handle_channel_creation(client, message)
                elif state.startswith("group_"):
                    await handle_group_creation(client, message)
                else:
                    # Неизвестное состояние, сбрасываем
                    user_state[user_id] = "main_menu"
                    await message.reply("Возврат в главное меню.", reply_markup=main_keyboard)
            except Exception as e:
                await message.reply(f"❌ Произошла ошибка: {str(e)}")
                user_state[user_id] = "main_menu"
        
        print("✅ Бот успешно запущен!")
        print(f"🤖 Токен бота: {BOT_TOKEN[:10]}...")
        print("📱 Ожидание сообщений...")
        
        await bot.run()
        
    except AccessTokenInvalid:
        print("❌ Ошибка: Неверный токен бота!")
        print("Проверьте BOT_TOKEN в файле .env")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Ошибка запуска: {str(e)}")
        sys.exit(1)
