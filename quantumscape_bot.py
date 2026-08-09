
import json
import html
import re
import os
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# INSTÄLLNINGAR
# ============================================================

RSS_URL = (
    "https://news.google.com/rss/search?"
    "q=QuantumScape&hl=en-US&gl=US&ceid=US:en"
)

# Discord-webhook hämtas från GitHub Secret
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL"
)

# Svensk tid
TIMEZONE = ZoneInfo("Europe/Stockholm")

# Daglig sammanfattning
DAILY_SUMMARY_HOUR = 18

# Filer som sparas i GitHub repository
SEEN_FILE = Path("quantumscape_seen.json")
DAILY_FILE = Path("quantumscape_daily.json")


# ============================================================
# RSS
# ============================================================

def get_rss():

    request = Request(
        RSS_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "QuantumScape-News-Monitor"
            ),
            "Accept": (
                "application/rss+xml, "
                "application/xml, "
                "text/xml, */*"
            )
        }
    )

    with urlopen(
        request,
        timeout=20
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="ignore"
        )


# ============================================================
# PARSA RSS
# ============================================================

def get_news():

    xml = get_rss()

    items = re.findall(
        r"<item\b[^>]*>(.*?)</item>",
        xml,
        re.DOTALL | re.IGNORECASE
    )

    news = []

    for item in items:

        title_match = re.search(
            r"<title\b[^>]*>(.*?)</title>",
            item,
            re.DOTALL | re.IGNORECASE
        )

        link_match = re.search(
            r"<link\b[^>]*>(.*?)</link>",
            item,
            re.DOTALL | re.IGNORECASE
        )

        if not title_match or not link_match:
            continue

        title = html.unescape(
            title_match.group(1).strip()
        )

        url = html.unescape(
            link_match.group(1).strip()
        )

        title = re.sub(
            r"<!\[CDATA\[(.*?)\]\]>",
            r"\1",
            title,
            flags=re.DOTALL
        )

        url = re.sub(
            r"<!\[CDATA\[(.*?)\]\]>",
            r"\1",
            url,
            flags=re.DOTALL
        )

        title = " ".join(
            title.split()
        )

        if not title or not url:
            continue

        news.append({
            "title": title,
            "url": url
        })

    return news


# ============================================================
# SEEN
# ============================================================

def load_seen():

    if not SEEN_FILE.exists():
        return set()

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return set(
                json.load(file)
            )

    except Exception:

        return set()


def save_seen(seen):

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            list(seen),
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# DAILY DATA
# ============================================================

def load_daily():

    if not DAILY_FILE.exists():

        return {
            "date": "",
            "articles": [],
            "summary_sent": False
        }

    try:

        with open(
            DAILY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return {
            "date": "",
            "articles": [],
            "summary_sent": False
        }


def save_daily(data):

    with open(
        DAILY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# DISCORD
# ============================================================

def send_discord(message):

    if not DISCORD_WEBHOOK_URL:

        raise RuntimeError(
            "DISCORD_WEBHOOK_URL saknas."
        )

    payload = json.dumps({
        "content": message
    }).encode("utf-8")

    request = Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "QuantumScape-News-Monitor"
        },
        method="POST"
    )

    with urlopen(
        request,
        timeout=20
    ) as response:

        if response.status not in (200, 204):

            raise RuntimeError(
                f"Discord HTTP-fel: {response.status}"
            )


# ============================================================
# NY HEADLINE
# ============================================================

def send_headline(article):

    message = (
        f"**[{article['title']}]"
        f"({article['url']})**"
    )

    send_discord(message)


# ============================================================
# DAGLIG SAMMANFATTNING
# ============================================================

def send_daily_summary(articles, today):

    lines = [
        f"**QuantumScape – dagens nyheter "
        f"({today})**",
        ""
    ]

    if not articles:

        lines.append(
            "Inga nya QuantumScape-nyheter idag."
        )

    else:

        for article in articles:

            lines.append(
                f"• [{article['title']}]"
                f"({article['url']})"
            )

    send_discord(
        "\n".join(lines)
    )


# ============================================================
# HUVUDPROGRAM
# ============================================================

def main():

    now = datetime.now(
        TIMEZONE
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    print(
        f"QuantumScape monitor "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"(Europe/Stockholm)"
    )

    # --------------------------------------------------------
    # Hämta RSS
    # --------------------------------------------------------

    news = get_news()

    print(
        f"RSS innehåller {len(news)} artiklar."
    )

    # --------------------------------------------------------
    # Ladda state
    # --------------------------------------------------------

    seen = load_seen()
    daily = load_daily()

    # --------------------------------------------------------
    # NY DAG
    # --------------------------------------------------------

    if daily.get("date") != today:

        daily = {
            "date": today,
            "articles": [],
            "summary_sent": False
        }

    # --------------------------------------------------------
    # FÖRSTA STARTEN
    # --------------------------------------------------------

    if not SEEN_FILE.exists():

        print(
            "Första körningen."
        )

        print(
            "Gamla artiklar registreras "
            "utan att skickas."
        )

        for article in news:

            seen.add(
                article["url"]
            )

        save_seen(seen)
        save_daily(daily)

        print(
            f"{len(seen)} gamla artiklar "
            "registrerades."
        )

        return

    # --------------------------------------------------------
    # NYA ARTIKLAR
    # --------------------------------------------------------

    new_articles = []

    for article in news:

        if article["url"] not in seen:

            new_articles.append(
                article
            )

    # Äldsta först
    new_articles.reverse()

    # --------------------------------------------------------
    # SKICKA NYA HEADLINES
    # --------------------------------------------------------

    for article in new_articles:

        print(
            f"NY: {article['title']}"
        )

        send_headline(
            article
        )

        seen.add(
            article["url"]
        )

        daily["articles"].append(
            article
        )

    # --------------------------------------------------------
    # SPARA STATE
    # --------------------------------------------------------

    save_seen(seen)
    save_daily(daily)

    # --------------------------------------------------------
    # DAGLIG SAMMANFATTNING
    # --------------------------------------------------------

    if (
        now.hour >= DAILY_SUMMARY_HOUR
        and not daily.get(
            "summary_sent",
            False
        )
    ):

        print(
            "Skickar dagens sammanfattning."
        )

        send_daily_summary(
            daily["articles"],
            today
        )

        daily["summary_sent"] = True

        save_daily(
            daily
        )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    print(
        f"Nya artiklar denna körning: "
        f"{len(new_articles)}"
    )

    print(
        "Körningen är klar."
    )


if __name__ == "__main__":
    main()
