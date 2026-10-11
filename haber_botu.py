"""KO Meydanı haber botu.

nttgame.com Knight Online haber sayfasını kontrol eder, yeni haberleri
Discord webhook'larına gönderir.
  GÜNCELLEME            -> WEBHOOK_GUNCELLEME (#güncelleme-notları)
  DUYURU, BAKIM, ETKİNLİK -> WEBHOOK_HABERLER   (#haberler)
"""
import hashlib
import json
import os
import re
import sys
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

NEWS_URL = "https://www.nttgame.com/knight/tr/news/"
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
COLOR = 0xE30A17
DATE_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")

CATEGORIES = {
    "DUYURU": ("📢", "WEBHOOK_HABERLER"),
    "GUNCELLEME": ("🛠️", "WEBHOOK_GUNCELLEME"),
    "BAKIM": ("🔧", "WEBHOOK_HABERLER"),
    "ETKINLIK": ("🎉", "WEBHOOK_HABERLER"),
}


def norm(text):
    """'Güncelleme' / 'GÜNCELLEME' / 'ETKİNLİK' -> 'GUNCELLEME' / 'ETKINLIK'."""
    text = unicodedata.normalize("NFKD", text.replace("ı", "i"))
    return "".join(c for c in text if not unicodedata.combining(c)).strip().upper()


def fetch_html():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9",
    }
    last = None
    for attempt in range(3):
        try:
            r = requests.get(NEWS_URL, headers=headers, timeout=30)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException as e:
            last = e
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"Sayfa alınamadı: {last}")


def category_count(node):
    return sum(1 for s in node.find_all(string=True) if norm(s) in CATEGORIES)


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    items, used = [], set()
    for label in soup.find_all(string=True):
        cat = norm(label)
        if cat not in CATEGORIES:
            continue
        # Kategori etiketinden yukarı çık: tek kategori + tarih içeren en geniş kutu = haber
        node, box = label.parent, None
        for _ in range(10):
            if node is None or node.name in ("body", "html"):
                break
            if category_count(node) > 1:
                break
            if DATE_RE.search(node.get_text(" ", strip=True)):
                box = node
            node = node.parent
        if box is None or id(box) in used:
            continue
        used.add(id(box))

        strings = [s for s in box.stripped_strings]
        date = DATE_RE.search(box.get_text(" ", strip=True)).group(1)
        rest = [s for s in strings if norm(s) != cat and s != date and len(s) > 2]
        if not rest:
            continue
        title = rest[0]
        body = " ".join(rest[1:]).replace(date, "").strip()
        img = box.find("img")
        thumb = img.get("src") if img else None
        if thumb and thumb.startswith("//"):
            thumb = "https:" + thumb
        uid = hashlib.sha1(f"{cat}|{title}|{date}".encode("utf-8")).hexdigest()[:16]
        items.append({"id": uid, "cat": cat, "label": label.strip(), "title": title,
                      "date": date, "body": body, "thumb": thumb})
    return items


def post(item):
    emoji, env = CATEGORIES[item["cat"]]
    url = os.environ.get(env) or os.environ.get("WEBHOOK_HABERLER")
    if not url:
        print(f"Webhook yok ({env}), atlandı: {item['title']}")
        return
    desc = item["body"]
    if len(desc) > 350:
        desc = desc[:347].rsplit(" ", 1)[0] + "…"
    embed = {
        "title": item["title"][:256],
        "url": NEWS_URL,
        "color": COLOR,
        "author": {"name": f"{emoji} {item['label'].upper()}"},
        "description": (desc + "\n\n" if desc else "") + f"[Haberin tamamı için tıkla]({NEWS_URL})",
        "fields": [{"name": "Tarih", "value": item["date"], "inline": True}],
        "footer": {"text": "KO Meydanı • nttgame.com"},
    }
    if item["thumb"]:
        embed["thumbnail"] = {"url": item["thumb"]}
    payload = {"username": "KO Meydanı Haber", "embeds": [embed],
               "allowed_mentions": {"parse": []}}
    for _ in range(5):
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            continue
        r.raise_for_status()
        print(f"Gönderildi [{item['label']}] {item['title']}")
        time.sleep(1.5)
        return
    raise SystemExit("Discord hız sınırı aşılamadı")


def main():
    items = parse(fetch_html())
    if not items:
        raise SystemExit("Hiç haber bulunamadı: sayfa yapısı değişmiş olabilir.")
    print(f"{len(items)} haber bulundu.")

    first_run = not os.path.exists(SEEN_FILE)
    seen = [] if first_run else json.load(open(SEEN_FILE, encoding="utf-8"))
    seen_set = set(seen)

    new = [i for i in items if i["id"] not in seen_set]
    if first_run:
        # İlk çalıştırma: kanalı doldurmamak için sadece en yeni haberi test olarak gönder
        new = new[:1]
    for item in reversed(new):  # eskiden yeniye
        post(item)

    seen = [i["id"] for i in items] + [s for s in seen if s not in {i["id"] for i in items}]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[:500], f, indent=0)
    print(f"{len(new)} yeni haber gönderildi.")


if __name__ == "__main__":
    sys.exit(main())
