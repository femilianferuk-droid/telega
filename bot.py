#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import (
    FloodWait, PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, ApiIdInvalid
)
import json
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ТОЛЬКО токен бота из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    print("Ошибка: BOT_TOKEN не найден в переменных окружения!")
    print("Создайте файл .env с содержимым: BOT_TOKEN=ваш_токен_бота")
    exit(1)

# Константы
CREATION_DELAY = 10  # Задержка между созданиями в секундах
DATA_DIR = "bot_data"

# Создаем папку для данных
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# Эмодзи
class Emoji:
    CHANNEL = "📢"
    GROUP = "👥"
    CHECK = "✅"
    CROSS = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    TIME = "⏱️"
    LINK = "🔗"
    ID = "🆔"
    SUCCESS = "🎉"
    WAIT = "⏳"
    ARROW = "➡️"
    BACK = "⬅️"
    MENU = "📋"
    KEY = "🔑"
    LOCK = "🔒"
    SETTINGS = "⚙️"
    USER = "👤"
    PHONE = "📱"
    CODE = "🔢"
    PASSWORD = "🔐"
    
    # Декоративные
    STAR = "⭐"
    ROCKET = "🚀"
    SPARKLES = "✨"
    HEART = "❤️"
    PARTY = "🎊"
    
    # Разделители
    LINE = "▬"
    POINT = "•"

class UserData:
    """Класс для хранения данных пользователя"""
    
    @staticmethod
    def get_filepath(user_id: int) -> str:
        return os.path.join(DATA_DIR, f"user_{user_id}.json")
    
    @staticmethod
    def save(user_id: int, data: dict):
        filepath = UserData.get_filepath(user_id)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения данных пользователя {user_id}: {e}")
            return False
    
    @staticmethod
    def load(user_id: int) -> dict:
        filepath = UserData.get_filepath(user_id)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки данных пользователя {user_id}: {e}")
            return []
    
    @staticmethod
    def update(user_id: int, **kwargs):
        data = UserData.load(user_id)
        data.update(kwargs)
        UserData.save(user_id, data)

class Bot:
    def __init__(self):
        # Для бота НЕ НУЖНЫ api_id и api_hash - только токен!
        self.app = Client(
            "channel_group_bot",
            bot_token=BOT_TOKEN
            # API ID и Hash НЕ передаются - бот работает только на токене
        )
        
        # Состояния пользователей
        self.user_states = {}
        self.creation_processes = {}
        self.auth_sessions = {}  # Временные данные для авторизации
    
    def register_handlers(self):
        """Регистрация обработчиков команд"""
        
        @self.app.on_message(filters.command("start"))
        async def start_command(client: Client, message: Message):
            await self.cmd_start(client, message)
        
        @self.app.on_message(filters.command("help"))
        async def help_command(client: Client, message: Message):
            await self.cmd_help(client, message)
        
        @self.app.on_message(filters.command("settings"))
        async def settings_command(client: Client, message: Message):
            await self.cmd_settings(client, message)
        
        @self.app.on_message(filters.command("channel"))
        async def channel_command(client: Client, message: Message):
            await self.cmd_create_channel(client, message)
        
        @self.app.on_message(filters.command("group"))
        async def group_command(client: Client, message: Message):
            await self.cmd_create_group(client, message)
        
        @self.app.on_message(filters.command("cancel"))
        async def cancel_command(client: Client, message: Message):
            await self.cmd_cancel(client, message)
        
        @self.app.on_message(filters.command("stop"))
        async def stop_command(client: Client, message: Message):
            await self.cmd_stop_creation(client, message)
        
        @self.app.on_callback_query()
        async def callback_handler(client: Client, callback_query: CallbackQuery):
            await self.handle_callback(client, callback_query)
        
        @self.app.on_message(filters.text & filters.private)
        async def text_handler(client: Client, message: Message):
            await self.handle_text(client, message)
    
    def create_progress_bar(self, current: int, total: int, length: int = 10) -> str:
        """Создает прогресс-бар"""
        filled = int(length * current / total)
        bar = "█" * filled + "░" * (length - filled)
        percentage = int((current / total) * 100)
        return f"{bar} {percentage}%"
    
    async def cmd_start(self, client: Client, message: Message):
        """Обработчик команды /start"""
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        
        # Загружаем данные пользователя
        user_data = UserData.load(user_id)
        
        welcome_text = f"""
{Emoji.PARTY} *Добро пожаловать в Channel Creator Bot!* {Emoji.ROCKET}

{Emoji.HEART} Привет, *{first_name}*!

{Emoji.STAR} *О боте:* {Emoji.STAR}
Я помогу вам создавать каналы и группы в Telegram.
Вам нужно добавить свой аккаунт Telegram через бота.

{Emoji.SETTINGS} *Для начала работы:*
{Emoji.POINT} Добавьте аккаунт через /settings
{Emoji.POINT} Создавайте каналы через /channel
{Emoji.POINT} Создавайте группы через /group

{Emoji.LINE*20}

{Emoji.INFO} Используйте /help для подробной информации
        """
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{Emoji.SETTINGS} Добавить аккаунт", callback_data="settings"),
             InlineKeyboardButton(f"{Emoji.INFO} Помощь", callback_data="help")],
            [InlineKeyboardButton(f"{Emoji.CHANNEL} Создать канал", callback_data="create_channel"),
             InlineKeyboardButton(f"{Emoji.GROUP} Создать группу", callback_data="create_group")],
            [InlineKeyboardButton(f"{Emoji.BACK} Выход", callback_data="exit")]
        ])
        
        await message.reply(welcome_text, parse_mode="Markdown", reply_markup=keyboard)
    
    async def cmd_help(self, client: Client, message: Message):
        """Обработчик команды /help"""
        help_text = f"""
{Emoji.SPARKLES} *Подробная справка* {Emoji.SPARKLES}

{Emoji.LINE*20}

*{Emoji.SETTINGS} Добавление аккаунта:*
1. Отправьте /settings
2. Введите API ID (число с my.telegram.org)
3. Введите API Hash (строка с my.telegram.org)
4. Введите номер телефона
5. Введите код подтверждения
6. (Если нужно) Введите пароль 2FA

*{Emoji.CHANNEL} Создание каналов:*
1. Отправьте /channel
2. Введите название (например: *Новости*)
3. Введите количество (например: *5*)
4. Подтвердите создание

*{Emoji.GROUP} Создание групп:*
1. Отправьте /group
2. Введите название (например: *Обсуждения*)
3. Введите количество (например: *3*)
4. Подтвердите создание

*{Emoji.TIME} Важно:*
{Emoji.POINT} Задержка между созданиями: *{CREATION_DELAY} сек*
{Emoji.POINT} Можно остановить процесс командой /stop
{Emoji.POINT} Для отмены действия используйте /cancel

{Emoji.LINE*20}

{Emoji.ROCKET} *Команды:*
/start - Главное меню
/settings - Добавить аккаунт
/channel - Создать каналы
/group - Создать группы
/stop - Остановить создание
/cancel - Отменить действие
/help - Эта справка
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{Emoji.BACK} В меню", callback_data="main_menu")]
        ])
        
        await message.reply(help_text, parse_mode="Markdown", reply_markup=keyboard)
    
    async def cmd_settings(self, client: Client, message: Message):
        """Обработчик команды /settings"""
        user_id = message.from_user.id
        user_data = UserData.load(user_id)
        
        has_account = 'session_name' in user_data
        
        if has_account:
            settings_text = f"""
{Emoji.SETTINGS} *Настройки аккаунта* {Emoji.SETTINGS}

{Emoji.LINE*20}

{Emoji.CHECK} *Аккаунт добавлен:*
{Emoji.USER} Имя: {user_data.get('name', 'Неизвестно')}
{Emoji.PHONE} Телефон: {user_data.get('phone', 'Неизвестно')}

{Emoji.LINE*20}

{Emoji.INFO} Для добавления нового аккаунта нажмите "Добавить".
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.USER} Добавить новый аккаунт", callback_data="add_account")],
                [InlineKeyboardButton(f"{Emoji.BACK} В меню", callback_data="main_menu")]
            ])
        else:
            settings_text = f"""
{Emoji.SETTINGS} *Добавление аккаунта* {Emoji.SETTINGS}

{Emoji.LINE*20}

{Emoji.WARNING} *Аккаунт не добавлен!*

Для работы бота необходимо добавить ваш аккаунт Telegram.

{Emoji.KEY} *Шаг 1:* Введите API ID
(число с my.telegram.org)
            """
            
            # Устанавливаем состояние
            self.user_states[user_id] = {'state': 'waiting_api_id'}
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.INFO} Как получить API", url="https://my.telegram.org")],
                [InlineKeyboardButton(f"{Emoji.BACK} Отмена", callback_data="cancel")]
            ])
        
        await message.reply(settings_text, parse_mode="Markdown", reply_markup=keyboard)
    
    async def cmd_create_channel(self, client: Client, message: Message):
        """Обработчик команды /channel"""
        user_id = message.from_user.id
        user_data = UserData.load(user_id)
        
        # Проверяем наличие аккаунта
        if 'session_name' not in user_data:
            error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Аккаунт не добавлен!

Сначала добавьте аккаунт через /settings
            """
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.SETTINGS} Добавить аккаунт", callback_data="settings")]
            ])
            await message.reply(error_text, parse_mode="Markdown", reply_markup=keyboard)
            return
        
        # Проверяем, не запущен ли уже процесс
        if user_id in self.creation_processes and self.creation_processes[user_id].get('running'):
            error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Уже запущен процесс создания!

Используйте /stop для остановки текущего процесса.
            """
            await message.reply(error_text, parse_mode="Markdown")
            return
        
        # Запрашиваем название
        create_text = f"""
{Emoji.CHANNEL} *Создание каналов* {Emoji.CHANNEL}

{Emoji.LINE*20}

{Emoji.ARROW} *Введите название для каналов:*

Например: *Новости*
(каналы будут называться: Новости 1, Новости 2, ...)

{Emoji.TIME} Между созданиями пауза *{CREATION_DELAY}* сек
        """
        
        self.user_states[user_id] = {'state': 'waiting_channel_name'}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{Emoji.BACK} Отмена", callback_data="cancel")]
        ])
        
        await message.reply(create_text, parse_mode="Markdown", reply_markup=keyboard)
    
    async def cmd_create_group(self, client: Client, message: Message):
        """Обработчик команды /group"""
        user_id = message.from_user.id
        user_data = UserData.load(user_id)
        
        # Проверяем наличие аккаунта
        if 'session_name' not in user_data:
            error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Аккаунт не добавлен!

Сначала добавьте аккаунт через /settings
            """
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.SETTINGS} Добавить аккаунт", callback_data="settings")]
            ])
            await message.reply(error_text, parse_mode="Markdown", reply_markup=keyboard)
            return
        
        # Проверяем, не запущен ли уже процесс
        if user_id in self.creation_processes and self.creation_processes[user_id].get('running'):
            error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Уже запущен процесс создания!

Используйте /stop для остановки текущего процесса.
            """
            await message.reply(error_text, parse_mode="Markdown")
            return
        
        # Запрашиваем название
        create_text = f"""
{Emoji.GROUP} *Создание групп* {Emoji.GROUP}

{Emoji.LINE*20}

{Emoji.ARROW} *Введите название для групп:*

Например: *Обсуждения*
(группы будут называться: Обсуждения 1, Обсуждения 2, ...)

{Emoji.TIME} Между созданиями пауза *{CREATION_DELAY}* сек
        """
        
        self.user_states[user_id] = {'state': 'waiting_group_name'}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{Emoji.BACK} Отмена", callback_data="cancel")]
        ])
        
        await message.reply(create_text, parse_mode="Markdown", reply_markup=keyboard)
    
    async def cmd_cancel(self, client: Client, message: Message):
        """Обработчик команды /cancel"""
        user_id = message.from_user.id
        
        if user_id in self.user_states:
            # Если есть временный клиент, отключаем его
            if 'temp_client' in self.user_states[user_id]:
                try:
                    await self.user_states[user_id]['temp_client'].disconnect()
                except:
                    pass
            del self.user_states[user_id]
            cancel_text = f"""
{Emoji.CHECK} *Действие отменено!*

{Emoji.ARROW} Используйте /start для возврата в главное меню.
            """
        else:
            cancel_text = f"""
{Emoji.INFO} *Нет активных действий*

{Emoji.ARROW} Используйте /start для просмотра команд.
            """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{Emoji.MENU} Главное меню", callback_data="main_menu")]
        ])
        
        await message.reply(cancel_text, parse_mode="Markdown", reply_markup=keyboard)
    
    async def cmd_stop_creation(self, client: Client, message: Message):
        """Обработчик команды /stop для остановки создания"""
        user_id = message.from_user.id
        
        if user_id in self.creation_processes and self.creation_processes[user_id].get('running'):
            self.creation_processes[user_id]['stop'] = True
            stop_text = f"""
{Emoji.WARNING} *Останавливаю процесс...*

{Emoji.TIME} Ожидайте завершения текущего создания.
            """
        else:
            stop_text = f"""
{Emoji.INFO} *Нет активных процессов создания*

{Emoji.ARROW} Используйте /channel или /group для начала.
            """
        
        await message.reply(stop_text, parse_mode="Markdown")
    
    async def handle_text(self, client: Client, message: Message):
        """Обработчик текстовых сообщений"""
        user_id = message.from_user.id
        text = message.text.strip()
        
        # Проверяем состояние пользователя
        if user_id not in self.user_states:
            unknown_text = f"""
{Emoji.INFO} *Неизвестная команда*

Используйте /start для просмотра доступных команд.
            """
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.MENU} Главное меню", callback_data="main_menu")]
            ])
            await message.reply(unknown_text, parse_mode="Markdown", reply_markup=keyboard)
            return
        
        state = self.user_states[user_id].get('state')
        
        if state == 'waiting_api_id':
            # Ждем API ID
            try:
                api_id = int(text)
                self.user_states[user_id]['api_id'] = api_id
                self.user_states[user_id]['state'] = 'waiting_api_hash'
                
                api_text = f"""
{Emoji.KEY} *API ID сохранен:* `{api_id}`

{Emoji.ARROW} *Теперь отправьте API Hash:*

(строка вида: `abc123def456...`)
                """
                await message.reply(api_text, parse_mode="Markdown")
                
            except ValueError:
                error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} API ID должен быть числом!

Попробуйте снова или отправьте /cancel для отмены.
                """
                await message.reply(error_text, parse_mode="Markdown")
        
        elif state == 'waiting_api_hash':
            # Ждем API Hash
            api_hash = text
            self.user_states[user_id]['api_hash'] = api_hash
            self.user_states[user_id]['state'] = 'waiting_phone'
            
            phone_text = f"""
{Emoji.LOCK} *API Hash сохранен*

{Emoji.PHONE} *Теперь введите номер телефона:*

(в международном формате, например: +79001234567)
            """
            await message.reply(phone_text, parse_mode="Markdown")
        
        elif state == 'waiting_phone':
            # Ждем номер телефона
            phone = text
            api_id = self.user_states[user_id]['api_id']
            api_hash = self.user_states[user_id]['api_hash']
            
            # Создаем временный клиент для авторизации
            session_name = f"user_{user_id}_temp"
            session_path = os.path.join(DATA_DIR, session_name)
            
            temp_client = Client(
                session_path,
                api_id=api_id,
                api_hash=api_hash,
                in_memory=False
            )
            
            try:
                await temp_client.connect()
                
                # Отправляем код
                self.user_states[user_id]['state'] = 'waiting_code'
                self.user_states[user_id]['phone'] = phone
                self.user_states[user_id]['temp_client'] = temp_client
                
                sent_code = await temp_client.send_code(phone)
                self.user_states[user_id]['phone_code_hash'] = sent_code.phone_code_hash
                
                code_text = f"""
{Emoji.CODE} *Код подтверждения отправлен!*

{Emoji.ARROW} Введите код из Telegram:
                """
                await message.reply(code_text, parse_mode="Markdown")
                
            except Exception as e:
                error_text = f"""
{Emoji.CROSS} *Ошибка отправки кода!*

{Emoji.WARNING} {str(e)}

Попробуйте снова или отправьте /cancel для отмены.
                """
                await message.reply(error_text, parse_mode="Markdown")
                await temp_client.disconnect()
                if user_id in self.user_states:
                    del self.user_states[user_id]
        
        elif state == 'waiting_code':
            # Ждем код подтверждения
            code = text
            temp_client = self.user_states[user_id].get('temp_client')
            phone = self.user_states[user_id]['phone']
            phone_code_hash = self.user_states[user_id]['phone_code_hash']
            
            try:
                try:
                    await temp_client.sign_in(phone, phone_code_hash, code)
                except SessionPasswordNeeded:
                    self.user_states[user_id]['state'] = 'waiting_2fa'
                    password_text = f"""
{Emoji.PASSWORD} *Требуется двухфакторная аутентификация!*

{Emoji.ARROW} Введите пароль 2FA:
                    """
                    await message.reply(password_text, parse_mode="Markdown")
                    return
                
                # Успешная авторизация
                me = await temp_client.get_me()
                
                # Сохраняем данные аккаунта
                session_name = f"user_{user_id}_account"
                session_path = os.path.join(DATA_DIR, session_name)
                
                # Переименовываем временную сессию
                temp_path = os.path.join(DATA_DIR, f"user_{user_id}_temp.session")
                new_path = os.path.join(DATA_DIR, f"user_{user_id}_account.session")
                if os.path.exists(temp_path):
                    os.rename(temp_path, new_path)
                
                user_data = {
                    'session_name': session_name,
                    'api_id': self.user_states[user_id]['api_id'],
                    'api_hash': self.user_states[user_id]['api_hash'],
                    'phone': phone,
                    'name': me.first_name,
                    'added_date': datetime.now().isoformat()
                }
                UserData.update(user_id, **user_data)
                
                await temp_client.disconnect()
                
                if user_id in self.user_states:
                    del self.user_states[user_id]
                
                success_text = f"""
{Emoji.SUCCESS} *Аккаунт успешно добавлен!* {Emoji.SUCCESS}

{Emoji.USER} Имя: {me.first_name}
{Emoji.PHONE} Телефон: {phone}

{Emoji.ROCKET} *Теперь вы можете:*
{Emoji.POINT} Создавать каналы через /channel
{Emoji.POINT} Создавать группы через /group
                """
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{Emoji.CHANNEL} Создать канал", callback_data="create_channel"),
                     InlineKeyboardButton(f"{Emoji.GROUP} Создать группу", callback_data="create_group")],
                    [InlineKeyboardButton(f"{Emoji.MENU} Главное меню", callback_data="main_menu")]
                ])
                
                await message.reply(success_text, parse_mode="Markdown", reply_markup=keyboard)
                
            except PhoneCodeInvalid:
                error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Неверный код подтверждения!

Попробуйте снова или отправьте /cancel для отмены.
                """
                await message.reply(error_text, parse_mode="Markdown")
            
            except PhoneCodeExpired:
                error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Код истек! Запросите новый.

Отправьте /settings для начала заново.
                """
                await message.reply(error_text, parse_mode="Markdown")
                if user_id in self.user_states:
                    del self.user_states[user_id]
        
        elif state == 'waiting_2fa':
            # Ждем пароль 2FA
            password = text
            temp_client = self.user_states[user_id].get('temp_client')
            phone = self.user_states[user_id]['phone']
            
            try:
                await temp_client.check_password(password)
                
                # Успешная авторизация
                me = await temp_client.get_me()
                
                # Сохраняем данные аккаунта
                session_name = f"user_{user_id}_account"
                session_path = os.path.join(DATA_DIR, session_name)
                
                # Переименовываем временную сессию
                temp_path = os.path.join(DATA_DIR, f"user_{user_id}_temp.session")
                new_path = os.path.join(DATA_DIR, f"user_{user_id}_account.session")
                if os.path.exists(temp_path):
                    os.rename(temp_path, new_path)
                
                user_data = {
                    'session_name': session_name,
                    'api_id': self.user_states[user_id]['api_id'],
                    'api_hash': self.user_states[user_id]['api_hash'],
                    'phone': phone,
                    'name': me.first_name,
                    'added_date': datetime.now().isoformat()
                }
                UserData.update(user_id, **user_data)
                
                await temp_client.disconnect()
                
                if user_id in self.user_states:
                    del self.user_states[user_id]
                
                success_text = f"""
{Emoji.SUCCESS} *Аккаунт успешно добавлен!* {Emoji.SUCCESS}

{Emoji.USER} Имя: {me.first_name}
{Emoji.PHONE} Телефон: {phone}

{Emoji.ROCKET} *Теперь вы можете:*
{Emoji.POINT} Создавать каналы через /channel
{Emoji.POINT} Создавать группы через /group
                """
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{Emoji.CHANNEL} Создать канал", callback_data="create_channel"),
                     InlineKeyboardButton(f"{Emoji.GROUP} Создать группу", callback_data="create_group")],
                    [InlineKeyboardButton(f"{Emoji.MENU} Главное меню", callback_data="main_menu")]
                ])
                
                await message.reply(success_text, parse_mode="Markdown", reply_markup=keyboard)
                
            except Exception as e:
                error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Неверный пароль 2FA!

Попробуйте снова или отправьте /cancel для отмены.
                """
                await message.reply(error_text, parse_mode="Markdown")
        
        elif state == 'waiting_channel_name':
            # Ждем название для каналов
            self.user_states[user_id]['name'] = text
            self.user_states[user_id]['state'] = 'waiting_channel_count'
            
            name_text = f"""
{Emoji.CHECK} *Название сохранено:* {text}

{Emoji.ARROW} *Введите количество каналов:*

(число от 1 до 20)
            """
            await message.reply(name_text, parse_mode="Markdown")
        
        elif state == 'waiting_channel_count':
            # Ждем количество каналов
            try:
                count = int(text)
                if count < 1 or count > 20:
                    raise ValueError
                
                name = self.user_states[user_id]['name']
                
                # Сохраняем данные
                self.user_states[user_id]['count'] = count
                self.user_states[user_id]['state'] = 'confirm_channel'
                
                total_time = count * CREATION_DELAY
                minutes = total_time // 60
                seconds = total_time % 60
                
                confirm_text = f"""
{Emoji.CHANNEL} *Подтверждение создания каналов*

{Emoji.LINE*20}

{Emoji.INFO} *Детали:*
{Emoji.POINT} Название: *{name}*
{Emoji.POINT} Количество: *{count}*
{Emoji.POINT} Время: *{minutes} мин {seconds} сек*

{Emoji.WARNING} *Внимание!*
Между созданиями пауза {CREATION_DELAY} секунд.
Процесс можно остановить командой /stop.

{Emoji.ARROW} *Подтвердите создание:*
                """
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{Emoji.CHECK} Да, создать", callback_data="confirm_channel"),
                     InlineKeyboardButton(f"{Emoji.CROSS} Нет, отмена", callback_data="cancel")]
                ])
                
                await message.reply(confirm_text, parse_mode="Markdown", reply_markup=keyboard)
                
            except ValueError:
                error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Введите число от 1 до 20!

Попробуйте снова или отправьте /cancel для отмены.
                """
                await message.reply(error_text, parse_mode="Markdown")
        
        elif state == 'waiting_group_name':
            # Ждем название для групп
            self.user_states[user_id]['name'] = text
            self.user_states[user_id]['state'] = 'waiting_group_count'
            
            name_text = f"""
{Emoji.CHECK} *Название сохранено:* {text}

{Emoji.ARROW} *Введите количество групп:*

(число от 1 до 20)
            """
            await message.reply(name_text, parse_mode="Markdown")
        
        elif state == 'waiting_group_count':
            # Ждем количество групп
            try:
                count = int(text)
                if count < 1 or count > 20:
                    raise ValueError
                
                name = self.user_states[user_id]['name']
                
                # Сохраняем данные
                self.user_states[user_id]['count'] = count
                self.user_states[user_id]['state'] = 'confirm_group'
                
                total_time = count * CREATION_DELAY
                minutes = total_time // 60
                seconds = total_time % 60
                
                confirm_text = f"""
{Emoji.GROUP} *Подтверждение создания групп*

{Emoji.LINE*20}

{Emoji.INFO} *Детали:*
{Emoji.POINT} Название: *{name}*
{Emoji.POINT} Количество: *{count}*
{Emoji.POINT} Время: *{minutes} мин {seconds} сек*

{Emoji.WARNING} *Внимание!*
Между созданиями пауза {CREATION_DELAY} секунд.
Процесс можно остановить командой /stop.

{Emoji.ARROW} *Подтвердите создание:*
                """
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{Emoji.CHECK} Да, создать", callback_data="confirm_group"),
                     InlineKeyboardButton(f"{Emoji.CROSS} Нет, отмена", callback_data="cancel")]
                ])
                
                await message.reply(confirm_text, parse_mode="Markdown", reply_markup=keyboard)
                
            except ValueError:
                error_text = f"""
{Emoji.CROSS} *Ошибка!*

{Emoji.WARNING} Введите число от 1 до 20!

Попробуйте снова или отправьте /cancel для отмены.
                """
                await message.reply(error_text, parse_mode="Markdown")
    
    async def handle_callback(self, client: Client, callback_query: CallbackQuery):
        """Обработчик callback запросов"""
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        await callback_query.answer()
        
        if data == "main_menu":
            # Возврат в главное меню
            await self.cmd_start(client, callback_query.message)
        
        elif data == "settings":
            # Настройки
            await self.cmd_settings(client, callback_query.message)
        
        elif data == "add_account":
            # Добавление нового аккаунта
            self.user_states[user_id] = {'state': 'waiting_api_id'}
            settings_text = f"""
{Emoji.SETTINGS} *Добавление нового аккаунта* {Emoji.SETTINGS}

{Emoji.LINE*20}

{Emoji.KEY} *Шаг 1:* Введите API ID
(число с my.telegram.org)
            """
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.BACK} Отмена", callback_data="cancel")]
            ])
            await callback_query.message.edit_text(settings_text, parse_mode="Markdown", reply_markup=keyboard)
        
        elif data == "help":
            # Помощь
            await self.cmd_help(client, callback_query.message)
        
        elif data == "create_channel":
            # Создание канала
            await self.cmd_create_channel(client, callback_query.message)
        
        elif data == "create_group":
            # Создание группы
            await self.cmd_create_group(client, callback_query.message)
        
        elif data == "cancel":
            # Отмена действия
            if user_id in self.user_states:
                # Если есть временный клиент, отключаем его
                if 'temp_client' in self.user_states[user_id]:
                    try:
                        await self.user_states[user_id]['temp_client'].disconnect()
                    except:
                        pass
                del self.user_states[user_id]
            
            cancel_text = f"""
{Emoji.CHECK} *Действие отменено!*

{Emoji.ARROW} Используйте /start для возврата в главное меню.
            """
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.MENU} Главное меню", callback_data="main_menu")]
            ])
            await callback_query.message.edit_text(cancel_text, parse_mode="Markdown", reply_markup=keyboard)
        
        elif data == "exit":
            # Выход
            exit_text = f"""
{Emoji.CHECK} *До свидания!* {Emoji.HEART}

Бот всегда готов помочь вам с созданием каналов и групп.

{Emoji.ARROW} Для возврата используйте /start
            """
            await callback_query.message.edit_text(exit_text, parse_mode="Markdown")
        
        elif data == "confirm_channel":
            # Подтверждение создания каналов
            if user_id not in self.user_states or self.user_states[user_id].get('state') != 'confirm_channel':
                return
            
            name = self.user_states[user_id]['name']
            count = self.user_states[user_id]['count']
            
            # Очищаем состояние
            del self.user_states[user_id]
            
            # Запускаем создание
            asyncio.create_task(self.create_channels(user_id, callback_query.message, name, count))
        
        elif data == "confirm_group":
            # Подтверждение создания групп
            if user_id not in self.user_states or self.user_states[user_id].get('state') != 'confirm_group':
                return
            
            name = self.user_states[user_id]['name']
            count = self.user_states[user_id]['count']
            
            # Очищаем состояние
            del self.user_states[user_id]
            
            # Запускаем создание
            asyncio.create_task(self.create_groups(user_id, callback_query.message, name, count))
    
    async def create_channels(self, user_id: int, message: Message, name: str, count: int):
        """Создание каналов"""
        user_data = UserData.load(user_id)
        
        if not user_data:
            await message.edit_text(f"{Emoji.CROSS} Данные аккаунта не найдены!")
            return
        
        # Создаем клиент для пользователя
        session_name = user_data['session_name']
        session_path = os.path.join(DATA_DIR, session_name)
        
        client = Client(
            session_path,
            api_id=user_data['api_id'],
            api_hash=user_data['api_hash'],
            in_memory=False
        )
        
        try:
            await client.connect()
            
            # Инициализируем процесс
            self.creation_processes[user_id] = {
                'running': True,
                'stop': False,
                'type': 'channel'
            }
            
            status_text = f"""
{Emoji.CHANNEL} *Начинаю создание {count} каналов...* {Emoji.ROCKET}

{Emoji.LINE*20}
            """
            status_msg = await message.edit_text(status_text, parse_mode="Markdown")
            
            created = 0
            failed = 0
            results = []
            
            for i in range(1, count + 1):
                # Проверяем остановку
                if self.creation_processes[user_id].get('stop'):
                    results.append(f"{Emoji.WARNING} Процесс остановлен пользователем")
                    break
                
                channel_name = f"{name} {i}"
                
                # Обновляем статус
                progress_bar = self.create_progress_bar(i, count)
                status_text = f"""
{Emoji.CHANNEL} *Создание каналов...* {Emoji.ROCKET}

{progress_bar}

{Emoji.CHECK} Создано: {created}
{Emoji.WAIT} Текущий: {i}/{count} - {channel_name}
{Emoji.TIME} Ожидание: {CREATION_DELAY} сек
                """
                await status_msg.edit_text(status_text, parse_mode="Markdown")
                
                try:
                    # Создаем канал
                    channel = await client.create_channel(
                        title=channel_name,
                        description=f"Канал {channel_name}"
                    )
                    
                    # Получаем ссылку
                    try:
                        invite_link = await client.export_chat_invite_link(channel.id)
                        link_text = f"[Ссылка]({invite_link})"
                    except:
                        link_text = "🔒 приватный"
                    
                    results.append(f"{Emoji.CHECK} {channel_name} - {link_text}")
                    created += 1
                    
                    # Задержка
                    if i < count and not self.creation_processes[user_id].get('stop'):
                        await asyncio.sleep(CREATION_DELAY)
                    
                except FloodWait as e:
                    wait = e.value
                    results.append(f"{Emoji.WAIT} {channel_name} - ожидание {wait}с")
                    await asyncio.sleep(wait)
                    i -= 1
                except Exception as e:
                    results.append(f"{Emoji.CROSS} {channel_name} - ошибка: {str(e)[:50]}")
                    failed += 1
            
            # Формируем результат
            result_text = f"""
{Emoji.SUCCESS} *Создание каналов завершено!* {Emoji.PARTY}

{Emoji.LINE*20}

{Emoji.CHECK} *Успешно:* {created}
{Emoji.CROSS} *Ошибок:* {failed}

{Emoji.LINE*20}

{Emoji.STAR} *Результаты:*
{chr(10).join(results[-10:])}
{Emoji.LINE*20}

{Emoji.ARROW} Используйте /start для продолжения
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.CHANNEL} Еще каналы", callback_data="create_channel"),
                 InlineKeyboardButton(f"{Emoji.GROUP} Создать группы", callback_data="create_group")],
                [InlineKeyboardButton(f"{Emoji.MENU} Главное меню", callback_data="main_menu")]
            ])
            
            await status_msg.edit_text(result_text, parse_mode="Markdown", reply_markup=keyboard)
            
        except Exception as e:
            error_text = f"""
{Emoji.CROSS} *Критическая ошибка!*

{Emoji.WARNING} {str(e)}

Проверьте настройки аккаунта и попробуйте снова.
            """
            await message.edit_text(error_text, parse_mode="Markdown")
        
        finally:
            # Очищаем процесс
            if user_id in self.creation_processes:
                del self.creation_processes[user_id]
            
            await client.disconnect()
    
    async def create_groups(self, user_id: int, message: Message, name: str, count: int):
        """Создание групп"""
        user_data = UserData.load(user_id)
        
        if not user_data:
            await message.edit_text(f"{Emoji.CROSS} Данные аккаунта не найдены!")
            return
        
        # Создаем клиент для пользователя
        session_name = user_data['session_name']
        session_path = os.path.join(DATA_DIR, session_name)
        
        client = Client(
            session_path,
            api_id=user_data['api_id'],
            api_hash=user_data['api_hash'],
            in_memory=False
        )
        
        try:
            await client.connect()
            
            # Инициализируем процесс
            self.creation_processes[user_id] = {
                'running': True,
                'stop': False,
                'type': 'group'
            }
            
            status_text = f"""
{Emoji.GROUP} *Начинаю создание {count} групп...* {Emoji.ROCKET}

{Emoji.LINE*20}
            """
            status_msg = await message.edit_text(status_text, parse_mode="Markdown")
            
            created = 0
            failed = 0
            results = []
            
            for i in range(1, count + 1):
                # Проверяем остановку
                if self.creation_processes[user_id].get('stop'):
                    results.append(f"{Emoji.WARNING} Процесс остановлен пользователем")
                    break
                
                group_name = f"{name} {i}"
                
                # Обновляем статус
                progress_bar = self.create_progress_bar(i, count)
                status_text = f"""
{Emoji.GROUP} *Создание групп...* {Emoji.ROCKET}

{progress_bar}

{Emoji.CHECK} Создано: {created}
{Emoji.WAIT} Текущий: {i}/{count} - {group_name}
{Emoji.TIME} Ожидание: {CREATION_DELAY} сек
                """
                await status_msg.edit_text(status_text, parse_mode="Markdown")
                
                try:
                    # Создаем супергруппу
                    group = await client.create_supergroup(
                        title=group_name,
                        description=f"Группа {group_name}"
                    )
                    
                    results.append(f"{Emoji.CHECK} {group_name} - ID: `{group.id}`")
                    created += 1
                    
                    # Задержка
                    if i < count and not self.creation_processes[user_id].get('stop'):
                        await asyncio.sleep(CREATION_DELAY)
                    
                except FloodWait as e:
                    wait = e.value
                    results.append(f"{Emoji.WAIT} {group_name} - ожидание {wait}с")
                    await asyncio.sleep(wait)
                    i -= 1
                except Exception as e:
                    results.append(f"{Emoji.CROSS} {group_name} - ошибка: {str(e)[:50]}")
                    failed += 1
            
            # Формируем результат
            result_text = f"""
{Emoji.SUCCESS} *Создание групп завершено!* {Emoji.PARTY}

{Emoji.LINE*20}

{Emoji.CHECK} *Успешно:* {created}
{Emoji.CROSS} *Ошибок:* {failed}

{Emoji.LINE*20}

{Emoji.STAR} *Результаты:*
{chr(10).join(results[-10:])}
{Emoji.LINE*20}

{Emoji.ARROW} Используйте /start для продолжения
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{Emoji.CHANNEL} Создать каналы", callback_data="create_channel"),
                 InlineKeyboardButton(f"{Emoji.GROUP} Еще группы", callback_data="create_group")],
                [InlineKeyboardButton(f"{Emoji.MENU} Главное меню", callback_data="main_menu")]
            ])
            
            await status_msg.edit_text(result_text, parse_mode="Markdown", reply_markup=keyboard)
            
        except Exception as e:
            error_text = f"""
{Emoji.CROSS} *Критическая ошибка!*

{Emoji.WARNING} {str(e)}

Проверьте настройки аккаунта и попробуйте снова.
            """
            await message.edit_text(error_text, parse_mode="Markdown")
        
        finally:
            # Очищаем процесс
            if user_id in self.creation_processes:
                del self.creation_processes[user_id]
            
            await client.disconnect()
    
    async def run(self):
        """Запуск бота"""
        try:
            print(f"{Emoji.ROCKET} Бот запускается...")
            
            # Регистрируем обработчики
            self.register_handlers()
            
            await self.app.start()
            
            # Получаем информацию о боте
            me = await self.app.get_me()
            print(f"{Emoji.SUCCESS} Бот @{me.username} успешно запущен!")
            print(f"{Emoji.INFO} Нажмите Ctrl+C для остановки")
            
            # Держим бота в работе
            await asyncio.Event().wait()
                
        except KeyboardInterrupt:
            print(f"\n{Emoji.WARNING} Остановка бота...")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            print(f"\n{Emoji.ERROR} Ошибка: {e}")
        finally:
            await self.app.stop()
            print(f"{Emoji.SUCCESS} Бот остановлен")

def main():
    """Точка входа"""
    bot = Bot()
    asyncio.run(bot.run())

if __name__ == "__main__":
    main()
