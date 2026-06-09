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

# Трекинг посетителей в памяти (сбрасывается при перезапуске)
_visitor_stats = {"users": set(), "starts": 0}


async def create_yukassa_payment(chat_id: int, user_name: str) -> str:
    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": str(float(PRICE_RUB)) + "0", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/" + str(BOT_USERNAME)
        },
        "capture": True,
        "description": BOOK_TITLE + " - " + user_name,
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


async def get_stats_text() -> str:
    # Продажи из ЮКасса
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.yookassa.ru/v3/payments",
                params={"status": "succeeded", "limit": 100},
                auth=(YUKASSA_SHOP_ID, YUKASSA_SECRET)
            )
            resp.raise_for_status()
            data = resp.json()
        items = data.get("items", [])
        count = len(items)
        if count > 0:
            total = sum(float(p["amount"]["value"]) for p in items)
            avg = total / count
            sales_text = (
                "Успешных оплат: " + str(count) + "\n"
                + "Сумма: " + str(int(total)) + " руб.\n"
                + "Средний чек: " + str(int(avg)) + " руб."
            )
        else:
            sales_text = "Оплат пока нет."
    except Exception as e:
        logger.error("Stats error: " + str(e))
        sales_text = "Ошибка загрузки данных ЮКасса."

    # Посетители из памяти
    unique = len(_visitor_stats["users"])
    total_starts = _visitor_stats["starts"]
    visitors_text = (
        "Уникальных пользователей: " + str(unique) + "\n"
        + "Всего запусков /start: " + str(total_starts) + "\n"
        + "(счётчик сбрасывается при перезапуске)"
    )

    return (
        "Статистика бота\n\n"
        + "Посещения:\n"
        + visitors_text + "\n\n"
        + "Продажи:\n"
        + sales_text
    )


async def send_invite_link(chat_id: int):
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            name="Buy tg:" + str(chat_id)
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "Открыть канал с книгой",
                url=invite.invite_link
            )
        ]])
        msg = (
            "Оплата получена! "
            "Спасибо за покупку!\n\n"
            "Нажмите кнопку ниже, "
            "чтобы войти в закрытый канал.\n\n"
            "Ссылка одноразовая — не передавайте другим."
        )
        await bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard)
        logger.info("Invite sent to " + str(chat_id))
    except Exception as e:
        logger.error("Error sending invite to " + str(chat_id) + ": " + str(e))
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "Оплата получена, "
                    "но произошла ошибка "
                    "при отправке ссылки. "
                    "Напишите нам."
                )
            )
        except Exception:
            pass


def welcome_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Что внутри книги?", callback_data="about_book"),
            InlineKeyboardButton("👤 Кто автор?", callback_data="about_author")
        ],
        [
            InlineKeyboardButton("📝 Читать отрывок", callback_data="excerpt")
        ]
    ])


def book_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👤 Об авторе", callback_data="about_author"),
        InlineKeyboardButton("💳 Купить — " + PRICE_RUB + " руб.", callback_data="buy")
    ]])


def buy_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 Купить книгу — " + PRICE_RUB + " руб.", callback_data="buy")
    ]])


def welcome_text(first_name):
    return (
        "Привет, " + first_name + "! 👋 Рада, что ты здесь.\n\n"
        "Это бот книги «Личное дно» — о женском "
        "высокофункциональном алкоголизме.\n\n"
        "Написана от первого лица. "
        "Для тех, у кого снаружи всё идеально: "
        "работа, статус, дети, красивая картинка. "
        "И именно поэтому так трудно признать, "
        "что происходит внутри.\n\n"
        "Это не мотивационный лозунг "
        "и не история мгновенного успеха. "
        "Это честный взгляд изнутри на то, "
        "как умные и успешные женщины "
        "попадают в ловушку отрицания, "
        "называя проблему «просто бокалом "
        "после тяжёлого дня»."
    )


def about_book_text():
    return (
        "Книга построена как исследование "
        "зависимости изнутри, без стыда и осуждения. "
        "Психологи уже используют её как библиотерапию "
        "для клиенток, которым сложно назвать "
        "вещи своими именами.\n\n"
        "Главные темы:\n\n"
        "• Ловушка интеллекта: почему умные люди "
        "дольше всех не замечают проблему\n"
        "• Механизм фасада: как годами держать "
        "лицо, пока внутренний мир рушится\n"
        "• Алкоголь как анестезия: почему он "
        "долго работал как стратегия от тревоги\n"
        "• Жизнь без иллюзий: как строить "
        "себя заново без героизма\n\n"
        "🎁 Внутри 4 практических приложения: "
        "самодиагностика, карта первых 30 дней, "
        "разбор триггеров и план на случай срыва.\n\n"
        "📄 PDF | 15 глав | На русском языке"
    )


def excerpt_part1_text():
    return (
        "Пролог: Лестница\n\n"
        "Эту ночь я помню фрагментами. Так всегда бывает "
        "с теми ночами, которые лучше бы не помнить вообще, "
        "но именно они почему-то остаются навсегда.\n\n"
        "Лестница. Чужой подъезд. Я.\n\n"
        "Падение было не красивым, не киношным. "
        "Не так, как героиня медленно оседает по стене "
        "с трагическим выражением лица. Нет. "
        "Это было то самое пьяное падение: "
        "неловкое, громкое, с полным отсутствием "
        "контроля над собственным телом. "
        "Тело, которое ещё несколько часов назад "
        "принадлежало вполне приличной женщине, "
        "решило больше не притворяться. "
        "Я упала так, как падают люди, "
        "которым уже всё равно, как они выглядят. "
        "И это, наверное, единственное, что алкоголь "
        "давал по-настоящему щедро и бесплатно: "
        "полное равнодушие к собственному достоинству.\n\n"
        "Мои дети это видели.\n\n"
        "Я написала это предложение и остановилась. "
        "Потому что даже сейчас, когда прошло время "
        "и всё изменилось, оно всё равно что-то "
        "делает где-то внутри. "
        "Не так остро, как раньше. Но делает.\n\n"
        "Они не закричали. Не убежали в панике "
        "искать взрослых и нормальных людей. "
        "Они подхватили меня под руки, молча, слаженно, "
        "как будто уже знали, что делать, "
        "как будто репетировали заранее, "
        "и отвели обратно к гостям. "
        "Потому что домой меня вести было бессмысленно. "
        "Потому что я была не в состоянии "
        "дойти до собственного дома.\n\n"
        "Замечательная картина, правда? "
        "Успешная женщина. Хорошая мать. "
        "Специалист, которого ценят на работе. "
        "Человек, у которого всё под контролем.\n\n"
        "Я не переношу ночевать в чужих домах. "
        "Это моя давняя особенность, которую я всегда "
        "считала вполне себе милой странностью. "
        "Своего рода тонкость организации. "
        "Мне нужно своё пространство: "
        "своя кровать, свои запахи, своя кружка утром, "
        "свои тапочки, которые точно там, где я их оставила. "
        "Чужое всегда ощущалось как что-то принудительное, "
        "из чего я сбегала при первой возможности, "
        "иногда невежливо рано, потому что невыносимо.\n\n"
        "Той ночью сбегать было некуда.\n\n"
        "Я лежала на чужом диване и притворялась, что сплю. "
        "За стеной разговаривали, звенела посуда, "
        "кто-то смеялся. Обычный вечер обычных людей, "
        "которые приняли у себя вдрабадан пьяную гостью "
        "и её детей, потому что что с этим ещё делать, "
        "не на лестнице же бросать.\n\n"
        "Мне хватило взгляда."
    )


def excerpt_part2_text():
    return (
        "Там, на том диване, той ночью "
        "я наконец остановила внутренний монолог "
        "про то, что у меня всё под контролем. "
        "Не потому что стала сильнее. "
        "А потому что сил притворяться уже не было. "
        "Это, кстати, единственное полезное свойство дна: "
        "там нечем прикрываться. "
        "Там остаёшься один на один с тем, что есть.\n\n"
        "Я не давала торжественных клятв. "
        "Не молилась. Не составляла план. "
        "Просто лежала и понимала одно: "
        "второй раз я не выдержу. "
        "Если снова окажусь здесь, "
        "останусь здесь навсегда. На этом дне.\n\n"
        "А навсегда на дне — нет. Это я не хотела.\n\n"
        "Это был страх. Самый обычный, "
        "примитивный, честный страх. "
        "Не сила духа, не осознанность, "
        "не духовный рост. Страх. "
        "И, как ни странно, этого оказалось достаточно.\n\n"
        "Утром было хуже, чем ночью. "
        "Это я говорю сразу, без смягчений, "
        "чтобы не было иллюзий. "
        "Решение не приносит облегчения. "
        "Решение приносит начало настоящей боли. "
        "Разница только в том, "
        "что эта боль в правильном направлении.\n\n"
        "Я встала. Умылась. Вышла. "
        "Сказала детям что-то незначительное. "
        "Мы поехали домой.\n\n"
        "Вчера была последняя бутылка. "
        "Я это знала. Никому не объявляла, просто знала.\n\n"
        "Я пишу эту книгу не потому, "
        "что стала примером для подражания "
        "и теперь хожу с просветлённым видом раздавать советы. "
        "Я по-прежнему та же женщина с теми же тараканами, "
        "только трезвая. Тараканы никуда не делись, "
        "они просто перестали быть незаметными.\n\n"
        "Я пишу её потому, что когда сама "
        "искала чей-то голос, живой, не причёсанный, "
        "без глянца и мотивационных выводов, "
        "найти было почти нечего. "
        "Особенно написанного женщиной, "
        "у которой внешне всё было в порядке. "
        "Работа, дети, статус. "
        "Которая не потеряла всё, но тихо теряла себя. "
        "И которая об этом говорит честно, "
        "без героизма и без жертвенности.\n\n"
        "Таких историй мало. "
        "А женщин, которым они нужны, много.\n\n"
        "Если ты держишь эту книгу, "
        "значит, что-то уже щёлкнуло. Или почти. "
        "Или стоишь прямо перед этим "
        "и ещё не знаешь, как назвать.\n\n"
        "Называй как хочешь. Главное, читай дальше."
    )


def about_author_text():
    return (
        "Привет! Меня зовут Наталья.\n\n"
        "Я не нарколог и не психотерапевт. "
        "Я женщина, которая прошла "
        "через всё это сама "
        "и теперь говорю об этом открыто.\n\n"
        "Я дипломированный инструктор НейроГрафики, "
        "занимаю руководящую должность "
        "в бюджетной сфере, "
        "веду личные консультации "
        "и практикую телесно-ориентированный подход.\n\n"
        "Эта книга выросла из того, "
        "чего мне самой отчаянно не хватало "
        "в самый тёмный период: "
        "живого, честного голоса "
        "без фраз «и тогда я всё поняла». "
        "Я делюсь тем, что знаю и прожила."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global BOT_USERNAME
    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username
        logger.info("Bot @" + str(BOT_USERNAME) + " started.")
        if WEBHOOK_URL:
            tg_webhook = WEBHOOK_URL + "/telegram/webhook"
            await bot.set_webhook(tg_webhook)
            logger.info("Webhook set: " + tg_webhook)
        else:
            logger.warning("WEBHOOK_URL not set.")
    except Exception as e:
        logger.error("Startup error: " + str(e))
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
            logger.info("Bot added to: " + str(chat.title) + " ID: " + str(chat.id))
            if ADMIN_ID:
                try:
                    await bot.send_message(
                        chat_id=int(ADMIN_ID),
                        text="Bot added to: " + str(chat.title) + "\nChannel ID: " + str(chat.id)
                    )
                except Exception as e:
                    logger.error("Could not notify admin: " + str(e))

    if update.message and update.message.text:
        text = update.message.text.strip()
        user = update.effective_user
        chat_id = update.effective_chat.id

        if text.startswith("/start"):
            # Трекинг посетителей
            _visitor_stats["users"].add(user.id)
            _visitor_stats["starts"] += 1
            await bot.send_message(
                chat_id=chat_id,
                text=welcome_text(user.first_name),
                reply_markup=welcome_keyboard()
            )

        elif text.startswith("/stats"):
            if str(user.id) == str(ADMIN_ID):
                stats = await get_stats_text()
                await bot.send_message(chat_id=chat_id, text=stats)
            else:
                await bot.send_message(chat_id=chat_id, text="Нет доступа.")

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

        elif query.data == "excerpt":
            await bot.send_message(
                chat_id=chat_id,
                text=excerpt_part1_text()
            )
            await bot.send_message(
                chat_id=chat_id,
                text=excerpt_part2_text(),
                reply_markup=buy_keyboard()
            )

        elif query.data == "buy":
            try:
                payment_url = await create_yukassa_payment(chat_id, user.first_name)
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "💳 Оплатить " + PRICE_RUB + " руб.",
                        url=payment_url
                    )
                ]])
                await bot.send_message(
                    chat_id=chat_id,
                    text="Ваша ссылка на оплату готова!",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error("Payment error: " + str(e))
                await bot.send_message(
                    chat_id=chat_id,
                    text="Ошибка при создании ссылки. Попробуйте позже."
                )

    return {"ok": True}


@app.post("/yukassa/webhook")
async def yukassa_webhook(request: Request):
    body = await request.json()
    logger.info("YuKassa webhook: " + json.dumps(body))
    event = body.get("event")
    payment = body.get("object", {})
    if event == "payment.succeeded":
        metadata = payment.get("metadata", {})
        chat_id_str = metadata.get("telegram_chat_id")
        if chat_id_str:
            await send_invite_link(int(chat_id_str))
    return {"status": "ok"}


@app.get("/setup-webhook")
async def setup_webhook():
    if not WEBHOOK_URL:
        return {"status": "error", "detail": "WEBHOOK_URL not set"}
    tg_webhook = WEBHOOK_URL + "/telegram/webhook"
    await bot.set_webhook(tg_webhook)
    return {"status": "webhook set", "url": tg_webhook}


@app.get("/")
async def health():
    return {"status": "running", "bot": BOT_USERNAME}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
