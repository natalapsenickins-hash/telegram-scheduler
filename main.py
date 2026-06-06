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
BOOK_TITLE       = os.getenv("BOOK_TITLE", "Lichnoe Dno")
ADMIN_ID         = os.getenv("ADMIN_ID", "")
AUTHOR_PHOTO_ID  = os.getenv("AUTHOR_PHOTO_ID", "")

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
            InlineKeyboardButton(
                "Открыть канал с книгой",
                url=invite.invite_link
            )
        ]])
        msg = (
            "✅ Оплата получена! "
            "Спасибо за покупку!\n\n"
            "Нажмите кнопку ниже, "
            "чтобы войти "
            "в закрытый канал.\n\n"
            "⚠️ Ссылка одноразовая "
            "— не передавайте другим."
        )
        await bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard)
        logger.info(f"Invite sent to {chat_id}")
    except Exception as e:
        logger.error(f"Error sending invite to {chat_id}: {e}")
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "Оплата получена, "
                    "но произошла ошибка "
                    "при отправке ссылки. "
                    "Напишите нам — разберёмся."
                )
            )
        except Exception:
            pass


def welcome_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Что внутри книги?", callback_data="about_book"),
            InlineKeyboardButton("👤 Кто автор?", callback_data="about_author"),
        ],
        [
            InlineKeyboardButton("📄 Читать отрывок", callback_data="sample"),
        ],
    ])


def book_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Об авторе", callback_data="about_author"),
            InlineKeyboardButton("📄 Читать отрывок", callback_data="sample"),
        ],
        [
            InlineKeyboardButton(f"💳 Купить — {PRICE_RUB} ₽", callback_data="buy"),
        ],
    ])


def buy_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"💳 Купить книгу — {PRICE_RUB} ₽", callback_data="buy")
    ]])


def welcome_text(first_name):
    return (
        f"Привет, {first_name}! 👋 Рада, что ты здесь.\n\n"
        "Это бот книги «Личное дно» "
        "— о женском "
        "высокофункциональном "
        "алкоголизме.\n\n"
        "Написана от первого лица. "
        "Для тех, у кого снаружи "
        "всё идеально: "
        "работа, статус, дети, "
        "красивая картинка. "
        "И именно поэтому "
        "так трудно признать, "
        "что происходит внутри.\n\n"
        "Это не мотивационный "
        "лозунг и не история "
        "мгновенного успеха. "
        "Это честный взгляд "
        "изнутри на то, "
        "как умные "
        "и успешные женщины "
        "попадают в ловушку "
        "отрицания, "
        "называя проблему "
        "«просто бокалом "
        "после тяжёлого дня»."
    )


def about_book_text():
    return (
        "Книга построена как "
        "исследование "
        "зависимости "
        "изнутри, без стыда "
        "и осуждения. "
        "Психологи уже "
        "используют её "
        "как библиотерапию "
        "для клиенток, "
        "которым сложно "
        "назвать вещи "
        "своими именами.\n\n"
        "Главные темы:\n\n"
        "• Ловушка интеллекта: "
        "почему умные люди "
        "дольше всех "
        "не замечают проблему\n"
        "• Механизм фасада: "
        "как годами держать "
        "лицо, пока "
        "внутренний мир рушится\n"
        "• Алкоголь как анестезия: "
        "почему он долго "
        "работал как "
        "стратегия "
        "от тревоги, и чем "
        "это опасно\n"
        "• Жизнь без иллюзий: "
        "что происходит, "
        "когда убираешь "
        "допинг, и как "
        "строить себя "
        "заново без героизма\n\n"
        "🎁 Внутри 4 практических "
        "приложения: "
        "самодиагностика, "
        "карта первых 30 дней, "
        "разбор триггеров "
        "и план действий "
        "на случай срыва.\n\n"
        "📄 PDF | 15 глав | На русском языке"
    )


def sample_text():
    return (
        "📄 <b>Отрывок из книги «Личное дно»</b>\n\n"
        "Алкоголь работал.\n\n"
        "Я напишу это ещё раз, потому что это важно: "
        "алкоголь работал. Это не преувеличение "
        "и не оправдание, это факт. Он снимал напряжение. "
        "Делал вечера мягче и теплее. Выключал тревожный "
        "фоновый шум в голове — тот самый нескончаемый "
        "список всего, что нужно сделать, о чём нужно "
        "подумать, за что нужно беспокоиться. Дети, работа, "
        "деньги, здоровье, отношения, завтра, послезавтра, "
        "через год. У меня этот шум, кажется, не останавливался "
        "никогда. Я к нему привыкла настолько, что считала "
        "его нормой.\n\n"
        "Алкоголь это выключал. На несколько часов — тишина. "
        "Не абсолютная, но достаточная.\n\n"
        "Для женщины с напряжённой работой, детьми, кучей "
        "всего, что нужно держать под контролем, это не мелочь. "
        "Это реальное, ощутимое, немедленное облегчение. "
        "И именно поэтому это так опасно. Потому что ты "
        "не принимаешь деструктивное решение — ты принимаешь "
        "решение, которое работает. Прямо сейчас. Каждый раз. "
        "Без осечек.\n\n"
        "И именно это делает зависимость такой трудной "
        "для остановки. Не потому что человек слабый. "
        "А потому что инструмент рабочий.\n\n"
        "Пока не перестаёт.\n\n"
        "А когда перестаёт, ты уже так долго им пользовалась, "
        "что других инструментов просто нет. Ты не умеешь иначе. "
        "Ты не знаешь, что делать с тревогой без бокала. "
        "Не знаешь, как расслабиться без него. Не знаешь, "
        "как провести пятничный вечер, как пережить особенно "
        "тяжёлый вторник, как просто посидеть в тишине "
        "и не потянуться за чем-то.\n\n"
        "Это не слабость характера. Повторю это ещё раз, "
        "потому что это важно — и потому что сама себе "
        "говорила противоположное слишком долго. Это не слабость. "
        "Это выученная беспомощность. Это отсутствие "
        "инструментов, которые никто не давал, потому что "
        "зачем — вот же готовый, в магазине за углом, "
        "работает немедленно.\n\n"
        "✂️ <i>Конец отрывка</i>"
    )


def about_author_text():
    return (
        "Привет! Меня зовут Наталья.\n\n"
        "Я не нарколог "
        "и не психотерапевт. "
        "Я женщина, "
        "которая "
        "прошла "
        "через "
        "всё это сама "
        "и теперь "
        "говорю "
        "об этом открыто.\n\n"
        "Я дипломированный "
        "инструктор "
        "НейроГрафики, "
        "занимаю "
        "руководящую "
        "должность "
        "в бюджетной сфере, "
        "веду личные "
        "консультации "
        "и практикую "
        "телесно-ориентированный "
        "подход.\n\n"
        "Эта книга "
        "выросла "
        "из того, "
        "чего мне самой "
        "отчаянно "
        "не хватало "
        "в самый "
        "тёмный период: "
        "живого, честного "
        "голоса без фраз "
        "«и тогда "
        "я всё поняла». "
        "Я делюсь "
        "тем, что "
        "знаю "
        "и прожила."
    )


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
            await bot.send_message(
                chat_id=chat_id,
                text=welcome_text(user.first_name),
                reply_markup=welcome_keyboard()
            )

    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        user = query.from_user
        await query.answer()

        if query.data == "about_book":
            await bot.send_message(
                chat_id=chat_id,
                text=about_book_text(),
                reply_markup=book_keyboard()
            )

        elif query.data == "about_author":
            if AUTHOR_PHOTO_ID:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=AUTHOR_PHOTO_ID,
                    caption=about_author_text(),
                    reply_markup=buy_keyboard()
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=about_author_text(),
                    reply_markup=buy_keyboard()
                )

        elif query.data == "sample":
            await bot.send_message(
                chat_id=chat_id,
                text=sample_text(),
                parse_mode="HTML",
                reply_markup=buy_keyboard()
            )

        elif query.data == "buy":
            try:
                payment_url = await create_yukassa_payment(chat_id, user.first_name)
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        f"💳 Оплатить {PRICE_RUB} ₽",
                        url=payment_url
                    )
                ]])
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "Ваша личная "
                        "ссылка "
                        "на оплату "
                        "— готова!"
                    ),
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Payment error: {e}")
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "Ошибка "
                        "при создании "
                        "ссылки. "
                        "Попробуйте позже."
                    )
                )

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
