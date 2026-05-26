import os
import logging
import uuid
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN        = os.getenv("BOT_TOKEN", "")
CHANNEL_ID       = os.getenv("CHANNEL_ID", "")
YUKASSA_SHOP_ID  = os.getenv("YUKASSA_SHOP_ID", "")
YUKASSA_SECRET   = os.getenv("YUKASSA_SECRET_KEY", "")
PRICE_RUB        = os.getenv("PRICE_RUB", "990")
WEBHOOK_URL      = os.getenv("WEBHOOK_URL", "")
BOOK_TITLE       = os.getenv("BOOK_TITLE", "Kniga")
ADMIN_ID         = os.getenv("ADMIN_ID", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
BOT_USERNAME = None


async def create_yukassa_payment(chat_id: int, user_name: str) -> str:
    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{float(PRICE_RUB):.2f}", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{BOT_USERNAME}"
        },
        "capture": True,
        "description": f"{BOOK_TITLE} - {user_name}",
        "metadata": {"telegram_chat_id": str(chat_id)}
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            auth=(YUKASSA_SHOP_ID, YUKASSA_SECRET),
            headers={"Idempotence-Key": idempotence_key}
        )
        resp.raise_for_status()
    return resp.json()["confirmation"]["confirmation_url"]


async def send_invite_link(chat_id: int):
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name=f"Buy tg:{chat_id}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Открыть канал с книгой", url=invite.invite_link)
        ]])
        msg = (
            "✅ Оплата получена! "
            "Спасибо за покупку!\n\n"
            "Нажмите кнопку ниже, "
            "чтобы войти в закрытый канал.\n\n"
            "⚠️ Ссылка одноразовая "
            "— не передавайте другим."
        )
        await bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard)
        logger.info(f"Invite link sent to {chat_id}")
    except Exception as e:
        logger.error(f"Error sending invite to {chat_id}: {e}")
        try:
            err_msg = (
                "Оплата получена, "
                "но произошла ошибка "
                "при отправке ссылки. "
                "Напишите нам — разберёмся."
            )
            await bot.send_message(chat_id=chat_id, text=err_msg)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global BOT_USERNAME
    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username
        logger.info(f"Bot @{BOT_USERNAME} started.")
        if WEBHOOK_URL:
            tg_webhook = f"{WEBHOOK_URL}/telegram/webhook"
            await bot.set_webhook(tg_webhook)
            logger.info(f"Webhook set: {tg_webhook}")
        else:
            logger.warning("WEBHOOK_URL not set.")
    except Exception as e:
        logger.error(f"Startup error: {e}")
    yield
    logger.info("Bot stopped.")


app = FastAPI(lifespan=lifespan)


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)

    if update.my_chat_member:
        chat = update.my_chat_member.chat
        new_status = update.my_chat_member.new_chat_member.status
        if new_status in ("administrator", "member"):
            logger.info(f"Bot added to: {chat.title} (ID: {chat.id})")
            if ADMIN_ID:
                try:
                    await bot.send_message(
                        chat_id=int(ADMIN_ID),
                        text=f"Bot added to: {chat.title}\nChannel ID: {chat.id}"
                    )
                except Exception as e:
                    logger.error(f"Could not notify admin: {e}")

    if update.message and update.message.text:
        text = update.message.text.strip()
        user = update.effective_user
        chat_id = update.effective_chat.id

        if text.startswith("/start"):
            try:
                payment_url = await create_yukassa_payment(chat_id, user.first_name)
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        f"Оплатить {PRICE_RUB} ₽",
                        url=payment_url
                    )
                ]])
                greeting = (
                    f"Привет, {user.first_name}! 👋\n\n"
                    f"Купите «{BOOK_TITLE}» за {PRICE_RUB} ₽.\n"
                    f"После оплаты вы автоматически "
                    f"получите ссылку для входа "
                    f"в закрытый канал."
                )
                await update.message.reply_text(greeting, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Payment error: {e}")
                err = "Ошибка при создании ссылки на оплату. Попробуйте позже."
                await update.message.reply_text(err)

    return {"ok": True}


@app.post("/yukassa/webhook")
async def yukassa_webhook(request: Request):
    body = await request.json()
    logger.info(f"YuKassa webhook: {json.dumps(body)}")
    event = body.get("event")
    payment = body.get("object", {})
    if event == "payment.succeeded":
        metadata = payment.get("metadata", {})
        chat_id_str = metadata.get("telegram_chat_id")
        if chat_id_str:
            await send_invite_link(int(chat_id_str))
    return {"status": "ok"}


@app.get("/")
async def health():
    return {"status": "running", "bot": BOT_USERNAME}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
