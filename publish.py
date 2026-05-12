"""
Автопостинг в Telegram-канал.
Запускается GitHub Actions каждый день в 20:00 по Москве.
Ищет папку posts/YYYY-MM-DD — если есть, публикует фото + текст.
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime
import pytz

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@bezanestezii_np"
MOSCOW = pytz.timezone("Europe/Moscow")

today = datetime.now(MOSCOW).strftime("%Y-%m-%d")
post_dir = Path("posts") / today

if not post_dir.exists():
    print(f"Нет поста на {today} — пропускаю.")
    exit(0)

marker = Path("published") / f"{today}.txt"
if marker.exists():
    print(f"Пост на {today} уже опубликован — пропускаю.")
    exit(0)

text_file = post_dir / "text.txt"
image_file = post_dir / "image.png"

if not text_file.exists():
    print(f"Нет text.txt в {post_dir}")
    exit(1)

text = text_file.read_text(encoding="utf-8").strip()

BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Публикуем фото (если есть) + текст
if image_file.exists():
    print(f"Отправляю фото из {image_file}...")
    with open(image_file, "rb") as f:
        r = requests.post(
            f"{BASE}/sendPhoto",
            data={"chat_id": CHANNEL},
            files={"photo": f},
            timeout=60,
        )
    if not r.json().get("ok"):
        print(f"Ошибка фото: {r.json()}")
        exit(1)
    print(f"Фото отправлено: message_id={r.json()['result']['message_id']}")
else:
    print("Картинки нет — только текст.")

print("Отправляю текст...")
r2 = requests.post(
    f"{BASE}/sendMessage",
    json={"chat_id": CHANNEL, "text": text},
    timeout=60,
)
if not r2.json().get("ok"):
    print(f"Ошибка текста: {r2.json()}")
    exit(1)
print(f"Текст отправлен: message_id={r2.json()['result']['message_id']}")

# Помечаем как опубликованный
Path("published").mkdir(exist_ok=True)
marker.write_text(f"published at {datetime.now(MOSCOW).isoformat()}")
print(f"Готово! Пост {today} опубликован.")
