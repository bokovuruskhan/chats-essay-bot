import datetime
from multiprocessing import Process

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from flask import render_template, request
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from telethon import TelegramClient
from telethon.sessions import SQLiteSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

import admin
from config import app, database, bot, dispatcher, api_id, api_hash, MESSAGES_COUNT, \
    SUBSCRIBE_GROUP_ID, LOG_FILE, ENCODING
from database import WebUser, save, Category, TelegramChat, get_all, find_by_id, delete, delete_all, TelegramUser, \
    ChatMessage, create_admin_user, FeedbackMessage, TelegramAccount
from gpt import get_essay

login_manager = LoginManager(app)
login_manager.login_view = "/login"


def log(msg, key=None):
    with open(LOG_FILE, "a", encoding=ENCODING) as log_file:
        log_file.write(f"{datetime.datetime.now()}, key={key}, msg={msg}\n")


def start_bot():
    if app.config["BOT_STATUS"] is False:
        bot_process = Process(target=bot_start_polling)
        bot_process.start()
        app.config["BOT_STATUS"] = True
        app.config["BOT_PROCESS_PID"] = bot_process.pid
        app.config["BOT_PROCESS"] = bot_process


@login_manager.user_loader
def load_user(user_id):
    return database.session.query(WebUser).get(user_id)


@app.get("/logout")
@login_required
def logout():
    logout_user()
    return show_login_form()


@app.get("/")
@login_required
def index(message=None, category=None):
    start_bot()
    chats = get_all(TelegramChat)
    categories = get_all(Category)
    if category is not None:
        chats = category.telegram_chats
    return render_template("index.html", feedback_messages=get_all(FeedbackMessage), chats_list=chats,
                           categories_list=categories, category=category,
                           bot_status=app.config["BOT_STATUS"],
                           message=message)


@app.post("/login")
def login():
    if current_user.is_authenticated:
        return index()
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        user = database.session.query(WebUser).filter(WebUser.username == username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return index()
        else:
            return show_login_form(message="Ошибка авторизации")


@app.get("/category/<category_id>")
@login_required
def by_category(category_id):
    category = find_by_id(Category, category_id)
    return index(category=category)


@app.post("/category/add")
@login_required
def add_category():
    name = request.form.get("name")
    save(Category(name=name))
    return index(message="Успешно добавлено.")


@app.post("/chat/add")
@login_required
async def add_chat():
    link = request.form.get("link")
    name = request.form.get("name")
    category_id = request.form.get("category_id")
    is_private = bool(request.form.get("is_private"))
    telegram_chat = TelegramChat(link=link, name=name, category_id=category_id, is_private=is_private)
    save(telegram_chat)
    await join_a_channel(telegram_chat.id)
    return index(message="Успешно добавлено.")


@app.post("/chat/delete")
@login_required
def delete_chat():
    _id = request.form.get("id")
    delete(TelegramChat.find_by_id(_id))
    return index(message="Успешно удалено.")


@app.post("/chat/prompt")
@login_required
def update_chat_prompt():
    _id = request.form.get("id")
    prompt = request.form.get("prompt")
    telegram_chat = TelegramChat.find_by_id(_id)
    telegram_chat.prompt = prompt
    save(telegram_chat)
    return index(message="Успешно обновлено.")


@app.get("/messages/clear")
@login_required
def clear_messages():
    delete_all(ChatMessage)
    return index()


@app.post("/message")
@login_required
async def send_message():
    text = request.form.get("text")
    for telegram_user in get_all(TelegramUser):
        await bot.send_message(telegram_user.id, text, parse_mode="HTML")
    return index(message="Успешно отправлено.")


@app.get("/subscribe/check")
async def subscribe_check():
    for telegram_user in get_all(TelegramUser):
        if len(telegram_user.subscribes) > 1:
            if await is_subscriber(telegram_user.id) is False:
                telegram_user.subscribes.clear()
                save(telegram_user)
    return index()


@app.get("/essay")
async def essay_start():
    await essay()
    return index()


@app.route("/login")
def show_login_form(message=None):
    return render_template("login.html", message=message)


async def gpt():
    for chat in get_all(TelegramChat):
        dialog = ""
        first_message_id = None
        messages = ChatMessage.get_unused_messages(chat.id)
        if len(messages) >= MESSAGES_COUNT:
            for message in messages:

                if first_message_id is None:
                    first_message_id = message.id

                text_message = f"{message.datetime}: {message.text}\n"
                dialog += text_message
                message.essay_flag = False
                save(message)
            try:
                dialog_essay = f"<a href='{chat.link}/{first_message_id}'><b>{chat.name}</b></a>\n\n" + get_essay(
                    chat.prompt,
                    dialog) + "\n"
                for telegram_user in get_all(TelegramUser):
                    if chat in telegram_user.subscribes:
                        try:
                            await bot.send_message(telegram_user.id, dialog_essay, parse_mode="HTML")
                        except Exception as e:
                            log(str(e), key=f"User:{telegram_user.id}")
            except Exception as e:
                log(str(e), key="OpenAI")
        else:
            log(f"messages count < {MESSAGES_COUNT}", key=f"Chat:{chat.link} ({chat.name})")


async def join_a_channel(chat_id):
    telegram_account = TelegramAccount.find_non_blocked_account()
    if telegram_account is not None:
        session = SQLiteSession(telegram_account.telethon_session_file)
        client = TelegramClient(session, api_id, api_hash)
        chat = TelegramChat.find_by_id(chat_id)
        async with client:
            if chat.is_private:
                channel_hash = chat.link.split('/')[-1]
                try:
                    await client(ImportChatInviteRequest(channel_hash))
                except Exception as e:
                    log(str(e), key=f"Chat:{chat.link} ({chat.name})")
            else:
                channel = await client.get_entity(chat.link)
                await client(JoinChannelRequest(channel))


async def essay():
    telegram_account = TelegramAccount.find_non_blocked_account()
    if telegram_account is not None:
        session = SQLiteSession(telegram_account.telethon_session_file)
        client = TelegramClient(session, api_id, api_hash)
        async with client:
            for chat in get_all(TelegramChat):
                try:
                    channel = await client.get_entity(chat.link)
                    messages = await client.get_messages(channel, MESSAGES_COUNT)
                    messages.reverse()
                    for i in messages:
                        if ChatMessage.find_by_id(i.id) is None and i.text is not None and i.id is not None:
                            save(ChatMessage(id=i.id, chat_id=chat.id, text=i.text, datetime=i.date))
                except Exception as e:
                    log(str(e), key=f"Chat:{chat.link} ({chat.name})")
        await gpt()


REGISTRATION_MESSAGE = "Зарегистрироваться"
SHOW_ALL_CHATS_MESSAGE = "Показать все чаты"
SHOW_ALL_CATEGORIES_MESSAGE = "Показать все категории чатов"
SHOW_MY_SUBSCRIBES_MESSAGE = "Показать мои подписки"
FEEDBACK_MESSAGE = "Обратная связь/Предложить чат"
HELP_MESSAGE = "Помощь (о проекте)"


async def is_user_subscribed_to_channel(channel_link: str, user_id: int) -> bool:
    """
    Проверяет, является ли пользователь с указанным user_id подписанным на канал по ссылке channel_link.
    :param channel_link: Ссылка на канал
    :param user_id: id пользователя
    :return: True, если пользователь подписан на канал, иначе False
    """

    chat = await bot.get_chat(channel_link)
    chat_member = await bot.get_chat_member(chat.id, user_id)
    return chat_member.status == types.ChatMemberStatus.MEMBER or chat_member.status == types.ChatMemberStatus. \
        ADMINISTRATOR or chat_member.status == types.ChatMemberStatus.CREATOR


async def is_subscriber(telegram_user_id):
    if await is_user_subscribed_to_channel(SUBSCRIBE_GROUP_ID, telegram_user_id):
        return True
    else:
        await bot.send_message(telegram_user_id,
                               f"Чтобы подписываться на более чем 1 канал, вы должны быть подписаны на "
                               f"{SUBSCRIBE_GROUP_ID}",
                               reply_markup=generate_reply_keyboard_for_user(telegram_user_id))
        return False


async def is_authorized(telegram_user_id):
    if TelegramUser.find_by_id(telegram_user_id) is not None:
        return True
    else:
        await bot.send_message(telegram_user_id,
                               f"Вы должны быть авторизованы, для использования бота",
                               reply_markup=generate_reply_keyboard_for_user(telegram_user_id))
        return False


def generate_reply_keyboard_for_user(user_id):
    reply_keyboard = ReplyKeyboardMarkup()
    if TelegramUser.find_by_id(user_id) is None:
        reply_keyboard.add(KeyboardButton(REGISTRATION_MESSAGE))
    else:
        reply_keyboard.add(KeyboardButton(SHOW_ALL_CHATS_MESSAGE))
        reply_keyboard.add(KeyboardButton(SHOW_ALL_CATEGORIES_MESSAGE))
        reply_keyboard.add(KeyboardButton(SHOW_MY_SUBSCRIBES_MESSAGE))
        reply_keyboard.add(KeyboardButton(FEEDBACK_MESSAGE))
        reply_keyboard.add(KeyboardButton(HELP_MESSAGE))
    return reply_keyboard


def get_all_chats_inline_keyboard_for_user(user_id):
    telegram_user = TelegramUser.find_by_id(user_id)
    inline_keyboard = InlineKeyboardMarkup()
    for chat in get_all(TelegramChat):
        if chat in telegram_user.subscribes:
            inline_keyboard.add(InlineKeyboardButton(f"{chat.name} ✅", callback_data=f"chat_{chat.id}"))
        else:
            inline_keyboard.add(InlineKeyboardButton(f"{chat.name}", callback_data=f"chat_{chat.id}"))
    return inline_keyboard


def get_chats_inline_keyboard_by_category_for_user(category_id, user_id):
    telegram_user = TelegramUser.find_by_id(user_id)
    inline_keyboard = InlineKeyboardMarkup()
    for chat in Category.find_by_id(category_id).telegram_chats:
        if chat in telegram_user.subscribes:
            inline_keyboard.add(InlineKeyboardButton(f"{chat.name} ✅", callback_data=f"chat_{chat.id}"))
        else:
            inline_keyboard.add(InlineKeyboardButton(f"{chat.name}", callback_data=f"chat_{chat.id}"))
    return inline_keyboard


def get_all_categories_inline_keyboard():
    inline_keyboard = InlineKeyboardMarkup()
    for category in get_all(Category):
        inline_keyboard.add(InlineKeyboardButton(f"{category.name}", callback_data=f"category_{category.id}"))
    return inline_keyboard


def get_chats_inline_keyboard_by_user_id(user_id):
    telegram_user = TelegramUser.find_by_id(user_id)
    inline_keyboard = InlineKeyboardMarkup()
    for chat in TelegramUser.find_by_id(user_id).subscribes:
        if chat in telegram_user.subscribes:
            inline_keyboard.add(InlineKeyboardButton(f"{chat.name} ✅", callback_data=f"chat_{chat.id}"))
        else:
            inline_keyboard.add(InlineKeyboardButton(f"{chat.name}", callback_data=f"chat_{chat.id}"))
    return inline_keyboard


def bot_start_polling():
    app.app_context().push()
    executor.start_polling(dispatcher=dispatcher, skip_updates=True)


@dispatcher.message_handler(commands=["start"])
async def bot_handler_start(message: types.Message):
    await message.reply("Выберите пункт меню", reply_markup=generate_reply_keyboard_for_user(message.from_user.id))


@dispatcher.message_handler(Text(REGISTRATION_MESSAGE))
async def bot_handler_registration(message: types.Message):
    if TelegramUser.find_by_id(message.from_user.id) is not None:
        await message.reply("Вы уже авторизованы", reply_markup=generate_reply_keyboard_for_user(message.from_user.id))
    else:
        save(TelegramUser(id=message.from_user.id))
        await message.reply("Успешная регистрация", reply_markup=generate_reply_keyboard_for_user(message.from_user.id))


class FeedbackFormStates(StatesGroup):
    feedback = State()


@dispatcher.message_handler(Text(FEEDBACK_MESSAGE))
async def bot_handler_feedback_message(message: types.Message):
    if await is_authorized(message.from_user.id):
        await message.reply(
            "Задайте свой вопрос")
        await FeedbackFormStates.feedback.set()


@dispatcher.message_handler(state=FeedbackFormStates.feedback)
async def feedback_handler(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        save(FeedbackMessage(text=message.text))
        data['feedback'] = message.text
    await state.finish()
    await message.answer("Спасибо за ваше обращение!")


@dispatcher.message_handler(Text(HELP_MESSAGE))
async def bot_handler_help_message(message: types.Message):
    if await is_authorized(message.from_user.id):
        await message.reply(
            "С помощью данного бота вы можете получать выдержки из различных телеграм-каналов. Воспользуйтесь списком "
            "представленных чатов, или используйте поиск по категориям. Уведомления с содержанием приходят один "
            "раз в час, в зависимости от нагруженности сервиса и количества новых сообщений")


@dispatcher.message_handler(Text(SHOW_MY_SUBSCRIBES_MESSAGE))
async def bot_handler_show_my_subscribes(message: types.Message):
    if await is_authorized(message.from_user.id):
        await message.reply("Мои подписки:",
                            reply_markup=get_chats_inline_keyboard_by_user_id(message.from_user.id))


@dispatcher.message_handler(Text(SHOW_ALL_CHATS_MESSAGE))
async def bot_handler_show_all_chats(message: types.Message):
    if await is_authorized(message.from_user.id):
        await message.reply("Выберите чат на который хотите подписаться",
                            reply_markup=get_all_chats_inline_keyboard_for_user(message.from_user.id))


@dispatcher.message_handler(Text(SHOW_ALL_CATEGORIES_MESSAGE))
async def bot_handler_show_all_categories(message: types.Message):
    if await is_authorized(message.from_user.id):
        await message.reply("Выберите категорию",
                            reply_markup=get_all_categories_inline_keyboard())


@dispatcher.callback_query_handler(lambda c: c.data in [f"chat_{i.id}" for i in get_all(TelegramChat)])
async def process_subscribe_callback_button(callback_query: types.CallbackQuery):
    if await is_authorized(callback_query.from_user.id):
        telegram_user = TelegramUser.find_by_id(callback_query.from_user.id)
        telegram_chat = TelegramChat.find_by_id(int(callback_query.data.split("_")[1]))
        if telegram_chat in telegram_user.subscribes:
            telegram_user.subscribes.remove(telegram_chat)
            await bot.send_message(callback_query.from_user.id, f"Вы ОТПИСАЛИСЬ от {telegram_chat.link}")
        else:
            if len(telegram_user.subscribes) >= 1:
                if await is_subscriber(callback_query.from_user.id):
                    telegram_user.subscribes.append(telegram_chat)
                    await bot.send_message(callback_query.from_user.id, f"Вы ПОДПИСАЛИСЬ на {telegram_chat.link}")
            else:
                telegram_user.subscribes.append(telegram_chat)
                await bot.send_message(callback_query.from_user.id, f"Вы ПОДПИСАЛИСЬ на {telegram_chat.link}")
        save(telegram_user)
    await bot.answer_callback_query(callback_query.id)


@dispatcher.callback_query_handler(lambda c: c.data in [f"category_{i.id}" for i in get_all(Category)])
async def process_category_callback_button(callback_query: types.CallbackQuery):
    if await is_authorized(callback_query.from_user.id):
        await bot.send_message(callback_query.from_user.id,
                               f"Выберите чат на который хотите подписаться "
                               f"({Category.find_by_id(int(callback_query.data.split('_')[1])).name})",
                               reply_markup=get_chats_inline_keyboard_by_category_for_user(
                                   int(callback_query.data.split("_")[1]), callback_query.from_user.id))
    await bot.answer_callback_query(callback_query.id)


if __name__ == "__main__":
    app.app_context().push()
    database.create_all()
    admin.config()
    create_admin_user()
    app.run(host="0.0.0.0")
