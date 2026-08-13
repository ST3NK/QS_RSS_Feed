import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from datetime import datetime
from zoneinfo import ZoneInfo

# ============================================================
# INSTÄLLNINGAR
# ============================================================

# Sökord för nyheter
SEARCH_QUERY = "QuantumScape"

# Hämta nycklar från GitHub Secrets
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Inställningar för tid och filer
TIMEZONE = ZoneInfo("Europe/Stockholm")
DAILY_SUMMARY_HOUR = 18
SEEN_FILE = Path("quantumscape_seen.json")
DAILY_FILE = Path("quantumscape_daily.json")

# ============================================================
# HÄMTA NYHETER FRÅN API
# ============================================================

def get_news():
    if not NEWS_API_KEY:
        raise RuntimeError("NEWS_API_KEY saknas i GitHub Secrets.")

    encoded_query = quote(SEARCH_QUERY)
    url = (
        "https://api.thenewsapi.com/v1/news/all"
        f"?api_token={NEWS_API_KEY}"
        f"&search={encoded_query}"
        "&language=en"
    )
    request = Request(url, headers={"User-Agent": "QuantumScape-Bot/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
            articles = data.get("data", [])
            return [
                {"title": art.get("title", "").strip(),
                 "url": art.get("url", "").strip()}
                for art in articles
            ]
    except Exception as e:
        print(f"Kunde inte hämta nyheter från API: {e}")
        return []
# ============================================================
# SEEN FILHANTERING
# ============================================================

def load_seen():
    if not SEEN_FILE.exists():
        return set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))
    except Exception:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as file:
        json.dump(list(seen), file, indent=2, ensure_ascii=False)

# ============================================================
# DAILY FILHANTERING
# ============================================================

def load_daily():
    if not DAILY_FILE.exists():
        return {"date": "", "articles": [], "summary_sent": False}
    try:
        with open(DAILY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"date": "", "articles": [], "summary_sent": False}

def save_daily(data):
    with open(DAILY_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

# ============================================================
# DISCORD FLÖDE
# ============================================================

def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL saknas.")

    payload = json.dumps({"content": message}).encode("utf-8")
    request = Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "QuantumScape-News-Monitor"
        },
        method="POST"
    )

    with urlopen(request, timeout=20) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f"Discord HTTP-fel: {response.status}")

def send_headline(article):
    message = f"**[{article['title']}]({article['url']})**"
    send_discord(message)

def send_daily_summary(articles, today):
    lines = [f"**QuantumScape – dagens nyheter ({today})**", ""]
    if not articles:
        lines.append("Inga nya QuantumScape-nyheter idag.")
    else:
        for article in articles:
            lines.append(f"• [{article['title']}]({article['url']})")
    send_discord("\n".join(lines))

# ============================================================
# HUVUDPROGRAM
# ============================================================

def main():
    now = datetime.now(TIMEZONE)
    today = now.strftime("%Y-%m-%d")

    print(f"QuantumScape monitor {now.strftime('%Y-%m-%d %H:%M:%S')} (Europe/Stockholm)")

    news = get_news()
    print(f"API:et hittade {len(news)} aktuella artiklar.")

    seen = load_seen()
    daily_data = load_daily()

    if daily_data["date"] != today:
        daily_data = {"date": today, "articles": [], "summary_sent": False}

    new_articles_found = False

    for article in reversed(news):
        url = article["url"]
        if not url or not article["title"]:
            continue
            
        if url not in seen:
            seen.add(url)
            daily_data["articles"].append(article)
            new_articles_found = True
            
            print(f"Ny artikel hittad: {article['title']}")
            try:
                send_headline(article)
            except Exception as e:
                print(f"Kunde inte skicka till Discord: {e}")

    if now.hour >= DAILY_SUMMARY_HOUR and not daily_data["summary_sent"]:
        print("Skickar daglig sammanfattning...")
        try:
            send_daily_summary(daily_data["articles"], today)
            daily_data["summary_sent"] = True
        except Exception as e:
            print(f"Kunde inte skicka sammanfattning: {e}")

    save_seen(seen)
    save_daily(daily_data)
    print("Körningen är klar.")

if __name__ == "__main__":
    main()
