"""
Генерация всех картинок для контент-плана.
"""
import requests
import urllib.parse
from pathlib import Path
import time

posts = [
    {
        "date": "2026-05-14",
        "prompt": (
            "person standing in front of large mirror, reflection looks uncertain or different, "
            "soft moody studio lighting, dark background, introspective mood, cinematic, "
            "shallow depth of field, photorealistic, vertical portrait, no text"
        ),
    },
    {
        "date": "2026-05-16",
        "prompt": (
            "three silhouettes of people standing in a triangle formation, "
            "dramatic tension between them, dark moody background with subtle light, "
            "cinematic composition, symbolic, photorealistic, vertical format, no text"
        ),
    },
    {
        "date": "2026-05-18",
        "prompt": (
            "person sitting at window looking out at beautiful sunny city view, "
            "expression is calm but slightly vacant, coffee cup in hand, warm light, "
            "contemplative mood, cinematic, shallow depth of field, photorealistic, vertical portrait, no text"
        ),
    },
    {
        "date": "2026-05-19",
        "prompt": (
            "person lying in bed looking at ceiling, soft morning light through curtains, "
            "peaceful but slightly melancholic atmosphere, warm tones, cinematic, "
            "shallow depth of field, photorealistic, vertical portrait, no text"
        ),
    },
    {
        "date": "2026-05-21",
        "prompt": (
            "person sitting at desk looking away toward window, open laptop ignored, "
            "cup of tea in hand, soft afternoon light, procrastination mood, "
            "cinematic warm tones, shallow depth of field, photorealistic, vertical portrait, no text"
        ),
    },
    {
        "date": "2026-05-23",
        "prompt": (
            "two people in a room, one person watching the other intently, "
            "subtle tension, soft moody interior light, one person unaware of being watched, "
            "cinematic composition, dark warm tones, photorealistic, vertical portrait, no text"
        ),
    },
    {
        "date": "2026-05-25",
        "prompt": (
            "person sitting completely still like a stone among swirling chaos around them, "
            "calm neutral expression, storm or motion blur surrounding them, "
            "dark dramatic background, cinematic, photorealistic, vertical portrait, no text"
        ),
    },
]

BASE = Path(r"C:\Users\наталья\Documents\telegram_scheduler\posts")

for i, post in enumerate(posts):
    out = BASE / post["date"] / "image.png"
    if out.exists() and out.stat().st_size > 20000:
        print(f"[{i+1}/7] {post['date']} — уже есть, пропускаю")
        continue

    encoded = urllib.parse.quote(post["prompt"])
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=832&height=1216&seed={42+i}&nologo=true&enhance=true&model=flux-realism"
    )
    print(f"[{i+1}/7] Генерирую {post['date']}...")
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            out.write_bytes(r.content)
            print(f"         Сохранено ({out.stat().st_size // 1024} KB)")
        else:
            print(f"         Ошибка {r.status_code}")
    except Exception as e:
        print(f"         Исключение: {e}")
    if i < len(posts) - 1:
        time.sleep(2)

print("\nГотово!")
