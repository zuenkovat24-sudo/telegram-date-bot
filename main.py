import os
import re
import json
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask
from threading import Thread

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# === НАСТРОЙКИ ===
logging.basicConfig(level=logging.INFO)
DATE_FORMAT = "%d.%m.%Y"
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1QzDByPjicYRB4csPMui86twJo8zcg5Ohq7KZDs5Yccg")
ADMIN_GROUP_ID = -1002925585648

# === GOOGLE SHEETS ===
def get_sheet():
    """Подключение к Google Sheets через JSON из переменной окружения"""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    service_account_info = os.getenv("SERVICE_ACCOUNT")

    if not service_account_info:
        raise RuntimeError("❌ Не найдена переменная SERVICE_ACCOUNT!")

    creds_dict = json.loads(service_account_info)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.sheet1

# === ПРОВЕРКА ФОРМАТА ДАТЫ ===
def is_valid_date(text: str) -> bool:
    if not re.fullmatch(r"\s*\d{2}\.\d{2}\.\d{4}\s*", text):
        return False
    try:
        datetime.strptime(text.strip(), DATE_FORMAT)
        return True
    except ValueError:
        return False

# === КОМАНДА /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎀 Добро пожаловать в студию декора *SVETLANA TELKOVA*!\n\n"
        "Мы создаём атмосферу праздника с любовью и вниманием к деталям 💐\n"
        "Оформляем президиумы, фотозоны, декор для частных клиентов и бизнеса.\n\n"
        "📅 Этот бот поможет узнать, свободна ли нужная дата для вашего события.\n\n"
        "Введите дату в формате ДД.ММ.ГГГГ (например 25.12.2025)",
        parse_mode="Markdown"
    )

# === ПРОВЕРКА ДАТЫ ===
async def check_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.message.from_user
    username = f"@{user.username}" if user.username else user.full_name

    if not is_valid_date(text):
        await update.message.reply_text(
            "Введите дату в формате ДД.ММ.ГГГГ (например 05.11.2025)"
        )
        return

    date_str = datetime.strptime(text, DATE_FORMAT).strftime(DATE_FORMAT)

    # Проверяем таблицу
    try:
        sheet = get_sheet()
        dates = sheet.col_values(1)
        booked = set(d.strip() for d in dates[1:] if d.strip())
    except Exception as e:
        logging.error(f"Ошибка доступа к Google Sheets: {e}")
        await update.message.reply_text("⚠️ Ошибка при подключении к таблице.")
        return

    # Ответ пользователю
    if date_str in booked:
        user_reply = (
            f"❌ К сожалению, дата {date_str} уже занята.\n"
            "Вы можете проверить другую дату или написать нам:\n"
            "[vk.me/vostorg_dzr](https://vk.me/vostorg_dzr)"
        )
        status = "❌ ЗАНЯТА"
    else:
        user_reply = (
            f"✅ Дата {date_str} свободна!\n"
            "Заполните, пожалуйста, анкету:\n"
            "[Открыть анкету](https://vk.com/app5619682_-220942261#713509)\n\n"
            "Либо напишите в личные сообщения:\n"
            "ВК: [https://vk.me/vostorg_dzr](https://vk.me/vostorg_dzr)\n"
            "ТГ: @TelkovaSvetlana\n\n"
            "_P.S.: Если мы с вами не связываемся, возможно у вас стоит запрет на входящие сообщения._\n"
            "Пожалуйста, напишите нам первыми 💬"
        )
        status = "✅ СВОБОДНА"

    await update.message.reply_text(user_reply, parse_mode="Markdown")

    # === УВЕДОМЛЕНИЕ В ГРУППУ АДМИНОВ ===
    try:
        if user.username:
            contact_link = f"[{username}](https://t.me/{user.username})"
        else:
            contact_link = f"{user.full_name} (ID: `{user.id}`)"

        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        admin_message = (
            "📩 *Новая проверка даты!*\n\n"
            f"👤 Пользователь: {contact_link}\n"
            f"📅 Дата: {date_str}\n"
            f"🕒 Время: {now}\n"
            f"📊 Статус: {status}"
        )

        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=admin_message,
            parse_mode="Markdown"
        )

    except Exception as e:
        logging.error(f"Ошибка при отправке в группу админов: {e}")

# === FLASK keep-alive для Render ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# === ТОЧКА ВХОДА ===
def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не найден BOT_TOKEN. Установите переменную окружения.")

    app_telegram = Application.builder().token(token).build()

    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_date))

    print("🤖 Bot is running...")
    app_telegram.run_polling(close_loop=False)

if __name__ == "__main__":
    keep_alive()  # 👈 запускает Flask, чтобы Render не выдавал ошибку порта
    main()



