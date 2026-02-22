import os
import re
import sqlite3
import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import SessionPasswordNeeded, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired
from pyrogram.enums import ChatType
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация
API_ID = 32480523
API_HASH = "147839735c9fa4e83451209e9b55cfc5"
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Берем токен из переменной окружения

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# Инициализация бота
app = Client(
    "account_manager_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# База данных
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT UNIQUE,
                  session_string TEXT,
                  status TEXT DEFAULT 'active',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Состояния пользователей
user_states = {}  # {user_id: {'state': 'waiting_phone', 'temp_client': Client}}
pending_codes = {}  # {phone: {'code': '12345', 'client': Client}}

# Временные клиенты для авторизации
temp_clients = {}

def get_account_client(phone):
    """Получить клиент для существующего аккаунта из базы"""
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    c.execute("SELECT session_string FROM accounts WHERE phone = ?", (phone,))
    result = c.fetchone()
    conn.close()
    
    if result:
        session_string = result[0]
        return Client(
            f"account_{phone}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_string
        )
    return None

def save_account_session(phone, session_string):
    """Сохранить сессию аккаунта в базу"""
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO accounts (phone, session_string, status) VALUES (?, ?, ?)",
        (phone, session_string, 'active')
    )
    conn.commit()
    conn.close()

def get_all_accounts():
    """Получить все активные аккаунты"""
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    c.execute("SELECT phone FROM accounts WHERE status = 'active'")
    accounts = [row[0] for row in c.fetchall()]
    conn.close()
    return accounts

# Команды бота
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Обработчик команды /start"""
    await message.reply_text(
        "👋 Добро пожаловать в бот для управления аккаунтами!\n\n"
        "📱 Доступные команды:\n"
        "/add_account - Добавить новый аккаунт\n"
        "/accounts - Список аккаунтов\n"
        "/get_code - Получить код из последнего сообщения\n"
        "/create_channel - Создать канал\n"
        "/help - Помощь"
    )

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Обработчик команды /help"""
    await message.reply_text(
        "📚 **Справка по использованию:**\n\n"
        "**Добавление аккаунта:**\n"
        "1. Нажмите /add_account\n"
        "2. Введите номер телефона в формате +79123456789\n"
        "3. Введите код подтверждения\n\n"
        "**Получение кода:**\n"
        "1. Нажмите /get_code\n"
        "2. Выберите аккаунт\n"
        "3. Бот найдет первый чат и покажет код из последнего сообщения\n\n"
        "**Создание канала:**\n"
        "1. Нажмите /create_channel\n"
        "2. Выберите аккаунт\n"
        "3. Введите название канала\n"
        "4. Введите описание (или пропустите)"
    )

@app.on_message(filters.command("add_account"))
async def add_account_start(client: Client, message: Message):
    """Начало добавления аккаунта"""
    user_id = message.from_user.id
    
    # Создаем временный клиент для авторизации
    temp_client = Client(
        f"temp_{user_id}_{datetime.now().timestamp()}",
        api_id=API_ID,
        api_hash=API_HASH,
        in_memory=True
    )
    
    user_states[user_id] = {
        'state': 'waiting_phone',
        'temp_client': temp_client
    }
    
    await message.reply_text(
        "📱 Введите номер телефона в международном формате (например, +79123456789):"
    )

@app.on_message(filters.command("accounts"))
async def list_accounts(client: Client, message: Message):
    """Список всех аккаунтов"""
    accounts = get_all_accounts()
    
    if not accounts:
        await message.reply_text("📭 Нет добавленных аккаунтов")
        return
    
    text = "📱 **Список аккаунтов:**\n\n"
    for i, phone in enumerate(accounts, 1):
        text += f"{i}. `{phone}`\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("get_code"))
async def get_code_command(client: Client, message: Message):
    """Получить код из первого чата"""
    accounts = get_all_accounts()
    
    if not accounts:
        await message.reply_text("❌ Сначала добавьте аккаунт через /add_account")
        return
    
    if len(accounts) == 1:
        # Если только один аккаунт, сразу используем его
        await process_get_code(message, accounts[0])
    else:
        # Если несколько, предлагаем выбрать
        text = "🔍 Выберите аккаунт для поиска кода:\n\n"
        for i, phone in enumerate(accounts, 1):
            text += f"{i}. `{phone}`\n"
        text += "\nОтправьте номер аккаунта (1, 2, ...):"
        
        user_states[message.from_user.id] = {
            'state': 'selecting_account_for_code',
            'accounts': accounts
        }
        await message.reply_text(text)

@app.on_message(filters.command("create_channel"))
async def create_channel_start(client: Client, message: Message):
    """Начало создания канала"""
    accounts = get_all_accounts()
    
    if not accounts:
        await message.reply_text("❌ Сначала добавьте аккаунт через /add_account")
        return
    
    if len(accounts) == 1:
        user_states[message.from_user.id] = {
            'state': 'creating_channel_title',
            'phone': accounts[0]
        }
        await message.reply_text("📢 Введите название для нового канала:")
    else:
        text = "📢 Выберите аккаунт для создания канала:\n\n"
        for i, phone in enumerate(accounts, 1):
            text += f"{i}. `{phone}`\n"
        text += "\nОтправьте номер аккаунта (1, 2, ...):"
        
        user_states[message.from_user.id] = {
            'state': 'selecting_account_for_channel',
            'accounts': accounts
        }
        await message.reply_text(text)

# Обработчик текстовых сообщений (для состояний)
@app.on_message(filters.text & filters.private)
async def handle_states(client: Client, message: Message):
    """Обработка состояний пользователя"""
    user_id = message.from_user.id
    text = message.text
    
    # Обработка ввода номера телефона
    if user_id in user_states and user_states[user_id]['state'] == 'waiting_phone':
        await process_phone_input(client, message)
    
    # Обработка ввода кода подтверждения
    elif user_id in user_states and user_states[user_id]['state'] == 'waiting_code':
        await process_code_input(client, message)
    
    # Выбор аккаунта для получения кода
    elif user_id in user_states and user_states[user_id]['state'] == 'selecting_account_for_code':
        try:
            idx = int(text) - 1
            accounts = user_states[user_id]['accounts']
            if 0 <= idx < len(accounts):
                phone = accounts[idx]
                del user_states[user_id]
                await process_get_code(message, phone)
            else:
                await message.reply_text("❌ Неверный номер. Попробуйте снова /get_code")
        except ValueError:
            await message.reply_text("❌ Пожалуйста, отправьте число")
    
    # Выбор аккаунта для создания канала
    elif user_id in user_states and user_states[user_id]['state'] == 'selecting_account_for_channel':
        try:
            idx = int(text) - 1
            accounts = user_states[user_id]['accounts']
            if 0 <= idx < len(accounts):
                phone = accounts[idx]
                user_states[user_id] = {
                    'state': 'creating_channel_title',
                    'phone': phone
                }
                await message.reply_text("📢 Введите название для нового канала:")
            else:
                await message.reply_text("❌ Неверный номер. Попробуйте снова /create_channel")
        except ValueError:
            await message.reply_text("❌ Пожалуйста, отправьте число")
    
    # Ввод названия канала
    elif user_id in user_states and user_states[user_id]['state'] == 'creating_channel_title':
        user_states[user_id]['title'] = text
        user_states[user_id]['state'] = 'creating_channel_description'
        await message.reply_text(
            "📝 Введите описание канала (или отправьте '-' чтобы пропустить):"
        )
    
    # Ввод описания канала и создание
    elif user_id in user_states and user_states[user_id]['state'] == 'creating_channel_description':
        phone = user_states[user_id]['phone']
        title = user_states[user_id]['title']
        description = None if text == '-' else text
        
        await message.reply_text("⏳ Создаю канал...")
        
        # Создаем канал
        await create_channel(message, phone, title, description)
        
        # Очищаем состояние
        del user_states[user_id]

async def process_phone_input(client: Client, message: Message):
    """Обработка ввода номера телефона"""
    user_id = message.from_user.id
    phone = message.text.strip()
    
    # Простая валидация номера
    if not re.match(r'^\+?\d{10,15}$', phone):
        await message.reply_text("❌ Неверный формат номера. Используйте формат: +79123456789")
        return
    
    temp_client = user_states[user_id]['temp_client']
    
    try:
        # Отправляем код подтверждения
        await temp_client.connect()
        sent_code = await temp_client.send_code(phone)
        
        # Сохраняем информацию
        user_states[user_id]['state'] = 'waiting_code'
        user_states[user_id]['phone'] = phone
        user_states[user_id]['phone_code_hash'] = sent_code.phone_code_hash
        
        await message.reply_text(
            "✅ Код подтверждения отправлен!\n"
            "📱 Введите код из SMS или Telegram:"
        )
        
    except PhoneNumberInvalid:
        await message.reply_text("❌ Неверный номер телефона")
        await temp_client.disconnect()
        del user_states[user_id]
    except Exception as e:
        await message.reply_text(f"❌ Ошибка: {str(e)}")
        await temp_client.disconnect()
        del user_states[user_id]

async def process_code_input(client: Client, message: Message):
    """Обработка ввода кода подтверждения"""
    user_id = message.from_user.id
    code = message.text.strip()
    
    state_data = user_states[user_id]
    temp_client = state_data['temp_client']
    phone = state_data['phone']
    phone_code_hash = state_data['phone_code_hash']
    
    try:
        # Пытаемся войти с кодом
        await temp_client.sign_in(
            phone_number=phone,
            phone_code_hash=phone_code_hash,
            phone_code=code
        )
        
        # Получаем строку сессии
        session_string = await temp_client.export_session_string()
        
        # Сохраняем в базу
        save_account_session(phone, session_string)
        
        await message.reply_text(
            f"✅ Аккаунт {phone} успешно добавлен!\n"
            f"Теперь вы можете использовать его для получения кодов и создания каналов."
        )
        
        # Закрываем временное соединение
        await temp_client.disconnect()
        del user_states[user_id]
        
    except SessionPasswordNeeded:
        # Если включена двухфакторка
        user_states[user_id]['state'] = 'waiting_password'
        await message.reply_text(
            "🔐 Включена двухфакторная аутентификация.\n"
            "Введите ваш пароль:"
        )
    except PhoneCodeInvalid:
        await message.reply_text("❌ Неверный код. Попробуйте снова /add_account")
        await temp_client.disconnect()
        del user_states[user_id]
    except PhoneCodeExpired:
        await message.reply_text("❌ Код истек. Запросите новый код через /add_account")
        await temp_client.disconnect()
        del user_states[user_id]
    except Exception as e:
        await message.reply_text(f"❌ Ошибка: {str(e)}")
        await temp_client.disconnect()
        del user_states[user_id]

async def process_get_code(message: Message, phone: str):
    """Поиск кода в первом чате аккаунта"""
    await message.reply_text(f"🔍 Ищу код в аккаунте {phone}...")
    
    try:
        # Получаем клиент для аккаунта
        account_client = get_account_client(phone)
        if not account_client:
            await message.reply_text("❌ Не удалось загрузить сессию аккаунта")
            return
        
        await account_client.connect()
        
        # Получаем первые 10 диалогов
        dialogs = []
        async for dialog in account_client.get_dialogs(limit=10):
            dialogs.append(dialog)
        
        if not dialogs:
            await message.reply_text("❌ Нет диалогов в этом аккаунте")
            await account_client.disconnect()
            return
        
        # Берем первый диалог (самый последний активный)
        first_chat = dialogs[0]
        chat_name = get_chat_name(first_chat.chat)
        
        # Получаем последние 20 сообщений из этого чата
        messages = []
        async for msg in account_client.get_chat_history(first_chat.chat.id, limit=20):
            if msg.text or msg.caption:
                messages.append(msg)
        
        if not messages:
            await message.reply_text(f"ℹ️ В чате {chat_name} нет текстовых сообщений")
            await account_client.disconnect()
            return
        
        # Ищем код в сообщениях (от последнего к первому)
        found_code = None
        code_message = None
        
        code_patterns = [
            r'\b\d{4,6}\b',  # 4-6 цифр подряд
            r'код[:\s]*(\d{4,6})',  # код: 123456
            r'code[:\s]*(\d{4,6})',  # code: 123456
            r'(\d{4,6})\s+[-\w]+',  # 123456 - код
        ]
        
        for msg in messages:
            text = msg.text or msg.caption
            if not text:
                continue
            
            text_lower = text.lower()
            
            # Проверяем разные паттерны
            for pattern in code_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Если группа захвата есть, берем её, иначе все совпадение
                    found_code = match.group(1) if match.groups() else match.group(0)
                    code_message = text
                    break
            
            if found_code:
                # Если нашли что-то похожее на код, проверяем контекст
                if re.match(r'^\d{4,6}$', found_code):
                    # Если это просто 4-6 цифр, проверяем есть ли рядом слова "код" или "code"
                    if 'код' in text_lower or 'code' in text_lower or 'пароль' in text_lower:
                        break
                    else:
                        # Если нет контекста, продолжаем искать
                        found_code = None
                        continue
                else:
                    break
        
        if found_code:
            # Формируем ответ
            response = (
                f"✅ **Найден код!**\n\n"
                f"📱 **Аккаунт:** `{phone}`\n"
                f"💬 **Чат:** {chat_name}\n"
                f"🔑 **Код:** `{found_code}`\n\n"
                f"📝 **Сообщение:**\n{code_message[:200]}"
            )
            if len(code_message) > 200:
                response += "..."
            
            await message.reply_text(response)
        else:
            await message.reply_text(
                f"❌ Код не найден в последних сообщениях чата {chat_name}\n"
                f"Проверьте другие чаты вручную через Telegram"
            )
        
        await account_client.disconnect()
        
    except Exception as e:
        await message.reply_text(f"❌ Ошибка при поиске кода: {str(e)}")

async def create_channel(message: Message, phone: str, title: str, description: str = None):
    """Создание канала от имени аккаунта"""
    try:
        # Получаем клиент для аккаунта
        account_client = get_account_client(phone)
        if not account_client:
            await message.reply_text("❌ Не удалось загрузить сессию аккаунта")
            return
        
        await account_client.connect()
        
        # Создаем канал
        channel = await account_client.create_channel(
            title=title,
            description=description
        )
        
        # Получаем ссылку на канал
        if channel.username:
            link = f"https://t.me/{channel.username}"
        else:
            # Если нет юзернейма, создаем пригласительную ссылку
            invite_link = await account_client.create_chat_invite_link(channel.id)
            link = invite_link.invite_link
        
        await message.reply_text(
            f"✅ **Канал успешно создан!**\n\n"
            f"📢 **Название:** {title}\n"
            f"🔗 **Ссылка:** {link}\n"
            f"📱 **Создан от:** `{phone}`"
        )
        
        await account_client.disconnect()
        
    except Exception as e:
        await message.reply_text(f"❌ Ошибка при создании канала: {str(e)}")

def get_chat_name(chat):
    """Получить название чата"""
    if chat.type == ChatType.PRIVATE:
        return f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "Пользователь"
    elif chat.type == ChatType.GROUP or chat.type == ChatType.SUPERGROUP:
        return chat.title or "Группа"
    elif chat.type == ChatType.CHANNEL:
        return chat.title or "Канал"
    else:
        return "Чат"

# Запуск бота
if __name__ == "__main__":
    print("🚀 Запуск бота...")
    init_db()
    print("✅ База данных инициализирована")
    print("🤖 Бот запущен. Нажмите Ctrl+C для остановки")
    app.run()
