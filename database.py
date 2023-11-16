from flask_login import UserMixin
from sqlalchemy import *
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

from config import database, MESSAGES_COUNT


class WebUser(database.Model, UserMixin):
    __tablename__ = "web_user"
    id = Column(Integer(), primary_key=True)
    username = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def find_by_username(username):
        return database.session.query(WebUser).filter(WebUser.username == username).first()


class Category(database.Model):
    __tablename__ = "category"
    id = Column(Integer(), primary_key=True)
    name = Column(String(255), nullable=False)
    telegram_chats = relationship("TelegramChat", backref="category")

    @staticmethod
    def find_by_id(category_id):
        return database.session.query(Category).filter(Category.id == category_id).first()


user_subscribes_table = database.Table("subscribes", database.Model.metadata,
                                       database.Column('telegram_user_id', database.Integer,
                                                       database.ForeignKey('telegram_user.id')),
                                       database.Column('telegram_chat_link', database.Integer,
                                                       database.ForeignKey('telegram_chat.link'))
                                       )


class FeedbackMessage(database.Model):
    __tablename__ = "feedback_message"
    id = Column(Integer(), primary_key=True)
    text = Column(String(1000))


class TelegramUser(database.Model):
    __tablename__ = "telegram_user"
    id = Column(Integer(), primary_key=True)
    subscribes = database.relationship("TelegramChat",
                                       secondary=user_subscribes_table)

    @staticmethod
    def find_by_id(_id):
        return database.session.query(TelegramUser).filter(TelegramUser.id == _id).first()


class TelegramAccount(database.Model):
    __tablename__ = "telegram_account"
    id = Column(Integer(), primary_key=True)
    telethon_session_file = Column(String(255), unique=True, nullable=False)
    is_blocked = Column(Boolean(), nullable=False, default=False)

    @staticmethod
    def find_non_blocked_account():
        return database.session.query(TelegramAccount).filter(TelegramAccount.is_blocked == False).first()


class TelegramChat(database.Model):
    __tablename__ = "telegram_chat"
    id = Column(Integer(), primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    link = Column(String(255), unique=True, nullable=False)
    is_private = Column(Boolean(), nullable=False, default=False)
    category_id = Column(Integer(), ForeignKey("category.id"))
    prompt = Column(String(1000), default="Сделай выдержку из этого диалога:")
    messages = relationship("ChatMessage", backref="telegram_chat")

    def __str__(self):
        return self.name

    @staticmethod
    def find_by_id(_id):
        return database.session.query(TelegramChat).filter(TelegramChat.id == _id).first()


class ChatMessage(database.Model):
    __tablename__ = "chat_message"
    id = Column(Integer(), primary_key=True)
    text = Column(Text)
    datetime = Column(DateTime())
    chat_id = Column(Integer(), ForeignKey("telegram_chat.id"))
    essay_flag = Column(Boolean(), default=True)

    @staticmethod
    def get_last_messages_by_chat_id(chat_id):
        return database.session.query(ChatMessage).filter(ChatMessage.essay_flag).filter(
            ChatMessage.chat_id == chat_id).order_by(
            ChatMessage.datetime).limit(MESSAGES_COUNT).all()

    @staticmethod
    def find_by_id(message_id):
        return database.session.query(ChatMessage).filter(ChatMessage.id == message_id).first()


def create_admin_user():
    if WebUser.find_by_username("admin") is None:
        web_user = WebUser(username="admin")
        web_user.set_password("admin")
        save(web_user)


def save(obj):
    try:
        database.session.add(obj)
        database.session.commit()
    except SQLAlchemyError as e:
        print(e)
        database.session.rollback()


def delete_all(obj_clas):
    database.session.query(obj_clas).delete()
    database.session.commit()


def delete(obj):
    database.session.delete(obj)
    database.session.commit()


def get_all(obj_class):
    return database.session.query(obj_class).all()


def find_by_id(obj_class, obj_id):
    return database.session.query(obj_class).filter(obj_class.id == obj_id).first()
