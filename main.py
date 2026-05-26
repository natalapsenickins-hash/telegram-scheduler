import os
import logging
import uuid
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes

# ──────────────────────────────────────────────
# Настройки (берутся из переменных окружения)
# ──────────────────────────────────────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN")           # Токен от BotFather
CHANNEL_ID       = os.getenv("CHANNEL_ID", "")      # ID канала, напр. -1001234567890
ADMIN_ID         = os.getenv("ADMIN_ID", "")        # Ваш личный Telegram ID (для служебных сообщений)
YUKASSA_SHOP_ID  = os.getenv("YUKASSA_SHOP_ID")     # ID магазина в ЮКассе
YUKASSA_SECRET   = os.getenv("YUKASSA_SECRET_KEY")  # Секретный ключ ЮКассы
PRICE_RUB        = os.getenv("PRICE_RUB", "990")    # Цена книги в рублях
WEBHOOK_URL      = os.getenv("WEBHOOK_URL")         # Ваш URL на Railway (без слэша в конце)
BOOK_TITLE       = os.getenv("BOOK_TITLE", "PDF-книга")  # Название книги

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
BOT_USERNAME = None  # Заполняется при старте


# ──────────────────────────────────────────────
# Создание платёжной ссылки ЮКасса
# ──────────────────────────────────────────────
async def create_yukassa_payment(chat_id: int, user_name: str) -> str:
    """Создаёт платёж в ЮКассе и возвращает ссылку на оплату."""
    idempotence_key = str(uuid.uuid4())

    payload = {
        "amount": {
            "value": f"{float(PRICE_RUB):.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{BOT_USERNAME}"  # Возврат в бота после оплаты
        },
        "capture": True,
        "description": f"{BOOK_TITLE} — {user_name}",
        "metadata": {
            "telegram_chat_id": str(chat_id)  # Сохраняем ID пользователя
        }
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            auth=(YUKASSA_SHOP_ID, YUKASSA_SECRET),
            headers={"Idempotence-Key": idempotence_key}
        )
        resp.raise_for_status()
        data = resp.json()

    return data["confirmation"]["confirmation_url"]


# ──────────────────────────────────────────────
# Отправка одноразовой ссылки-приглашения
# ──────────────────────────────────────────────
async def send_invite_link(chat_id: int):
    """Создаёт одноразовую ссылку в канал и отправляет покупателю."""
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,          # Одноразовая — нельзя передать другому
            name=f"Покупка tg:{chat_id}"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📖 Войти в канал с книгой", url=invite.invite_link)
        ]])

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ *Оплата прошла успешно!* Спасибо за покупку!\n\n"
                f"Нажмите кнопку ниже, чтобы войти в закрытый канал с {BOOK_TITLE}.\n\n"
                "⚠️ Ссылка *одноразовая* — не передавайте её другим людям."
            ),
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        logger.info(f"✅ Ссылка отправлена пользователю {chat_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка отправки ссылки пользователю {chat_id}: {e}")
        # Уведомляем пользователя, что что-то пошло не так
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "✅ Оплата получена, но произошла техническая ошибка при отправке ссылки.\n"
                    "Пожалуйста, напишите нам — мы разберёмся вручную."
                )
            )
        except Exception:
            pass


# ──────────────────────────────────────────────
# FastAPI приложение
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Настройка вебхука при запуске."""
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username

    tg_webhook = f"{WEBHOOK_URL}/telegram/webhook"
    await bot.set_webhook(tg_webhook)
    logger.info(f"🤖 Бот @{BOT_USERNAME} запущен. Вебхук: {tg_webhook}")
    yield
    logger.info("Бот остановлен.")

app = FastAPI(lifespan=lifespan)


# ──────────────────────────────────────────────
# Эндпоинт: вебхук от Telegram
# ──────────────────────────────────────────────
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)

    # Бот добавлен в новый чат/канал — сообщаем ID администратору
    if update.my_chat_member:
        chat = update.my_chat_member.chat
        new_status = update.my_chat_member.new_chat_member.status
        if new_status in ("administrator", "member"):
            msg = (
                f"✅ Бот добавлен в чат!\n"
                f"Название: {chat.title}\n"
                f"ID канала: <code>{chat.id}</code>\n\n"
                f"Скопируйте ID и добавьте в Railway как переменную CHANNEL_ID"
            )
            logger.info(f"Бот добавлен в чат {chat.title} (ID: {chat.id})")
            if ADMIN_ID:
                try:
                    await bot.send_message(chat_id=int(ADMIN_ID), text=msg, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение администратору: {e}")

    if update.message and update.message.text:
        text = update.message.text.strip()
        user = update.effective_user
        chat_id = update.effective_chat.id

        if text.startswith("/start"):
            try:
                payment_url = await create_yukassa_payment(chat_id, user.first_name)

                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        f"💳 Оплатить {PRICE_RUB} ₽",
                        url=payment_url
                    )
                ]])

                await update.message.reply_text(
                    f"Привет, {user.first_name}! 👋\n\n"
                    f"Здесь вы можете купить *{BOOK_TITLE}* за *{PRICE_RUB} ₽*.\n\n"
                    "После оплаты вы *автоматически* получите ссылку для входа в закрытый канал с книгой.",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Ошибка создания платежа: {e}")
                await update.message.reply_text(
                    "Произошла ошибка при создании ссылки на оплату. Попробуйте позже."
                )

    return {"ok": True}


# ──────────────────────────────────────────────
# Эндпоинт: вебхук от ЮКассы
# ───────────────────────────────────────────