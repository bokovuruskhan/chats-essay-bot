from sqlalchemy import inspect

from database import TelegramUser, TelegramChat, Category, ChatMessage, FeedbackMessage, TelegramAccount
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from config import app, database, APP_NAME


class TelegramUserView(ModelView):
    allow_pk = True
    column_list = [c_attr.key for c_attr in inspect(TelegramUser).mapper.column_attrs]


class ChatMessageView(ModelView):
    allow_pk = True
    column_list = [c_attr.key for c_attr in inspect(ChatMessage).mapper.column_attrs]


def config():
    admin = Admin(app, APP_NAME, template_mode="bootstrap4")
    admin.add_view(TelegramUserView(TelegramUser, database.session, "Пользователь"))
    admin.add_view(ModelView(TelegramChat, database.session, "Чаты"))
    admin.add_view(ModelView(Category, database.session, "Категории"))
    admin.add_view(ModelView(TelegramAccount, database.session, "Telegram аккаунты"))
    admin.add_view(ChatMessageView(ChatMessage, database.session, "Сообщения"))
    admin.add_view(ModelView(FeedbackMessage, database.session, "Обратная связь"))
