import requests, urllib.parse, time
from pathlib import Path

posts = [
    ("2026-05-26", "person standing in empty room wearing expensive suit, looking at their reflection in window, expression hollow despite success, dark moody interior, cinematic, photorealistic, vertical, no text"),
    ("2026-05-28", "two faces of the same person side by side, one glowing idealised, one shadowed, split contrast lighting, dark background, symbolic portrait, cinematic, photorealistic, vertical, no text"),
    ("2026-05-30", "person standing alone in modern minimalist apartment at night, city lights below, expression contemplative and slightly lost, everything material present but something missing, cinematic, photorealistic, vertical, no text"),
    ("2026-06-01", "person lying on couch watching phone screen glowing in dark room, warm light from screen, absorbed expression, solitary but not sad, cinematic, photorealistic, vertical, no text"),
    ("2026-06-02", "person lying on bed staring at ceiling in afternoon light, fully clothed, exhausted without reason, soft warm tones, cinematic, shallow depth of field, photorealistic, vertical, no text"),
    ("2026-06-04", "person at crossroads in a foggy landscape, two paths diverging, warm vs cold light, contemplative mood, cinematic, photorealistic, vertical, no text"),
    ("2026-06-06", "close-up of a cocoon hanging on bare branch, soft light, transformation metaphor, macro photography style, bokeh background, warm tones, vertical, no text"),
    ("2026-06-08", "person at crowded party standing slightly apart, blurred people around them in motion, they are sharp and still, disconnected feeling, cinematic, photorealistic, vertical, no text"),
    ("2026-06-09", "executive in expensive suit sitting alone at bar at night, whiskey glass in hand, city lights through window, successful but hollow expression, cinematic, photorealistic, vertical, no text"),
    ("2026-06-11", "person looking confidently into camera, warm natural light, calm self-assured expression, no props, simple background, cinematic portrait, photorealistic, vertical, no text"),
    ("2026-06-13", "adult person walking away from childhood home, looking back over shoulder, bittersweet expression, golden hour light, cinematic, photorealistic, vertical, no text"),
    ("2026-06-15", "compass on weathered wood in fog, pointing direction, moody atmospheric light, close-up macro, warm tones, symbolic, photorealistic, vertical, no text"),
    ("2026-06-16", "person standing at open door looking out, freedom visible outside, slight hesitation in posture, warm interior vs bright exterior, cinematic, photorealistic, vertical, no text"),
    ("2026-06-18", "person holding piece of paper with two columns written, thoughtful expression, simple desk, natural light, focused and calm, cinematic, photorealistic, vertical, no text"),
    ("2026-06-20", "two silhouettes facing each other, one reaching out, ambiguous whether in love or need, dramatic backlight, dark moody tones, cinematic, photorealistic, vertical, no text"),
    ("2026-06-22", "calm still water reflecting stormy sky above, contrast between surface peace and turbulence above, metaphor for acceptance, cinematic, photorealistic, vertical, no text"),
    ("2026-06-23", "person smiling warmly at others while alone expression shows fatigue, party or gathering setting, public face vs private exhaustion, cinematic, photorealistic, vertical, no text"),
    ("2026-06-25", "broken mirror showing fragmented reflection, some pieces show idealized image some show dark, dramatic lighting, symbolic, cinematic, photorealistic, vertical, no text"),
    ("2026-06-27", "person sitting alone at edge of cliff at dusk, four shadowy presences around them representing fears, contemplative atmosphere, cinematic, photorealistic, vertical, no text"),
    ("2026-06-29", "person sitting quietly in sunlit room, calm self-contained expression, warm golden light, no phone or distractions, simply present, cinematic, photorealistic, vertical, no text"),
    ("2026-06-30", "two people in same space but each in own world, one reading one on phone, subtle emotional distance despite physical closeness, cinematic, photorealistic, vertical, no text"),
    ("2026-07-02", "person standing in spotlight on stage, audience visible in darkness, expression shows need for validation, theatrical dramatic lighting, cinematic, photorealistic, vertical, no text"),
    ("2026-07-04", "hand reaching for bottle of whiskey on table, moment of decision, dramatic side lighting, dark moody atmosphere, cinematic, photorealistic, vertical, no text"),
    ("2026-07-06", "extreme close-up of hand pausing in mid-air, moment of hesitation before action, dramatic lighting, dark background, decisive instant frozen in time, cinematic, photorealistic, vertical, no text"),
]

BASE = Path(r"C:\Users\наталья\Documents\telegram_scheduler\posts")

for i, (date, prompt) in enumerate(posts):
    out = BASE / date / "image.png"
    if out.exists() and out.stat().st_size > 15000:
        print(f"[{i+1}/{len(posts)}] {date} — уже есть, пропускаю")
        continue
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=832&height=1216&seed={50+i}&nologo=true&enhance=true&model=flux-realism"
    print(f"[{i+1}/{len(posts)}] {date}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            out.write_bytes(r.content)
            print(f"{out.stat().st_size // 1024} KB")
        else:
            print(f"ошибка {r.status_code}")
    except Exception as e:
        print(f"исключение: {e}")
    if i < len(posts) - 1:
        time.sleep(1)

print("Готово!")
