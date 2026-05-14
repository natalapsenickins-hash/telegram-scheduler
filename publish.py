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

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()  # убираем случайный пробел/перенос из Secret
CHANNEL = "-1002124671575"  # числовой ID канала @bezanestezii_np
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

if image_file.exists():
    # Фото + текст одним постом (caption, лимит 1024 символа)
    if len(text) > 1024:
        print(f"ВНИМАНИЕ: текст {len(text)} символов > 1024, обрезаю до лимита.")
        text = text[:1021] + "..."
    img_size = image_file.stat().st_size
    print(f"Отправляю пост с фото... (файл: {image_file}, размер: {img_size} байт)")
    print(f"Токен (длина): {len(BOT_TOKEN)}, канал: {CHANNEL}")
    # Сначала тест sendMessage
    test_r = requests.post(f"{BASE}/sendMessage",
        json={"chat_id": CHANNEL, "text": "🔧 тест связи (удалить)"},
        timeout=30)
    print(f"sendMessage test: status={test_r.status_code}, ok={test_r.json().get('ok')}")
    if test_r.json().get("ok"):
        msg_id = test_r.json()["result"]["message_id"]
        requests.post(f"{BASE}/deleteMessage",
            json={"chat_id": CHANNEL, "message_id": msg_id}, timeout=10)
    # Теперь отправляем фото
    with open(image_file, "rb") as f:
        first_bytes = f.read(4)
        f.seek(0)
        print(f"Первые 4 байта файла: {first_bytes.hex()}")
        r = requests.post(
            f"{BASE}/sendPhoto",
            data={"chat_id": CHANNEL, "caption": text},
            files={"photo": ("photo.jpg", f, "image/jpeg")},
            timeout=60,
        )
    print(f"sendPhoto HTTP статус: {r.status_code}")
    print(f"sendPhoto ответ: {r.text[:500]}")
    if not r.json().get("ok"):
        print(f"Ошибка sendPhoto: {r.json()}")
        exit(1)
    print(f"Опубликовано: message_id={r.json()['result']['message_id']}")
else:
    # Только текст (лимит 4096 символов)
    print("Картинки нет, отправляю текст...")
    r = requests.post(
        f"{BASE}/sendMessage",
        json={"chat_id": CHANNEL, "text": text},
        timeout=60,
    )
    if not r.json().get("ok"):
        print(f"Ошибка: {r.json()}")
        exit(1)
    print(f"Опубликовано: message_id={r.json()['result']['message_id']}")

# Помечаем как опубликованный
Path("published").mkdir(exist_ok=True)
marker.write_text(f"published at {datetime.now(MOSCOW).isoformat()}")
print(f"Готово! Пост {today} опубликован.")
