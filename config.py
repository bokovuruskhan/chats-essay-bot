from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.files import JSONStorage
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

APP_NAME = "ChatsEssayBot"
MESSAGES_COUNT = 500
SCHEDULER_INTERVAL_SECONDS = 300
ENCODING = "utf-8"
LOG_FILE = "log.txt"
SUBSCRIBE_GROUP_ID = "@defievo"

app = Flask(APP_NAME, static_url_path="/static")
app.debug = True
app.config["SECRET_KEY"] = "\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR'\xa1\xa8"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["BOT_STATUS"] = False
app.config["BOT_PROCESS_PID"] = None
database = SQLAlchemy(app)

token = "6039799492:AAEBSARah__B49FlxdPYD6z4bmQnwLRLP1A"
api_id = 29411256
api_hash = "2b4e2863948713833500abef5d724104"
api_key = "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"

bot = Bot(token=token)
storage = JSONStorage("states.json")
dispatcher = Dispatcher(bot=bot, storage=storage)
