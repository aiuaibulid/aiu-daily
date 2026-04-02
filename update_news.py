#!/usr/bin/env python3
"""
AIU Daily News Updater
每天由 GitHub Actions 執行，抓取最新新聞並更新 index.html
使用 RSS 靜態源（不依賴 JS 渲染）+ MyMemory / Google Translate 翻譯
"""

import re
import time
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

TZ_TAIPEI = timezone(timedelta(hours=8))

# ── RSS 來源（靜態 XML，不需要 JavaScript）─────────────────────
RSS_SOURCES = [
    ("https://cointelegraph.com/rss",                    "CoinTelegraph"),
    ("https://decrypt.co/feed",                          "Decrypt"),
    ("https://www.coindesk.com/arc/outboundfeeds/rss/",  "CoinDesk"),
]

def parse_pub_datetime(raw):
    if not raw:
        return None

    text = raw.strip()

    # RFC-822 (most RSS feeds)
    try:
        dt = parsedate_to_datetime(text)
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # ISO-8601 (many Atom feeds)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def fetch_rss(url, source_name):
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AIUBot/1.0)"
        })
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        results = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=36)

        for item in items[:20]:
            title_el = item.find("title") or item.find("atom:title", ns)
            link_el  = item.find("link") or item.find("atom:link", ns)
            date_el  = (
                item.find("pubDate")
                or item.find("published")
                or item.find("updated")
                or item.find("atom:published", ns)
                or item.find("atom:updated", ns)
                or item.find("dc:date", ns)
            )

            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if len(title) < 10:
                continue

            link = ""
            if link_el is not None:
                link = (link_el.text or link_el.get("href") or "").strip()

            pub_time = parse_pub_datetime(date_el.text if date_el is not None else "")
            if pub_time and pub_time < cutoff:
                continue
            time_str = pub_time.astimezone(TZ_TAIPEI).strftime("%H:%M") if pub_time else ""

            results.append({
                "title": title,
                "url": link,
                "time": time_str,
                "source": source_name,
                "published_at": pub_time.isoformat() if pub_time else "",
            })

        results.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        print(f"✅ {source_name}: 抓到 {len(results)} 條")
        return results[:8]

    except Exception as e:
        print(f"⚠️ {source_name} 抓取失敗: {e}")
        return []


def fetch_news():
    merged = []
    seen = set()

    for url, name in RSS_SOURCES:
        items = fetch_rss(url, name)
        for item in items:
            dedupe_key = (item.get("url") or item.get("title") or "").strip().lower()
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            merged.append(item)

    if merged:
        merged.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        return merged[:8]

    print("❌ 所有來源均失敗，保留舊新聞")
    return []


# ── 翻譯（MyMemory 主力 + Google 備用）─────────────────────────
def translate_one(title):
    """MyMemory 優先（不封鎖機房 IP），Google Translate 備用。"""
    # 主要：MyMemory API（免費、無需 key、機房 IP 可用）
    try:
        resp = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|zh-CN"},
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AIUBot/1.0)"}
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("responseStatus") == 200:
            result = data["responseData"]["translatedText"]
            if result and result.strip() and result.strip() != title:
                return result.strip()
    except Exception as e:
        print(f"  ⚠️ MyMemory 失敗: {e}")

    # 備用：Google Translate 非官方端點
    try:
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=en&tl=zh-CN&dt=t&q={quote(title)}"
        )
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        data = resp.json()
        result = "".join(part[0] for part in data[0] if part[0])
        if result:
            return result.strip()
    except Exception as e:
        print(f"  ⚠️ Google Translate 失敗: {e}")

    return title  # 兩個都失敗則保留原文


def translate_to_zh(titles):
    translated = []
    for i, title in enumerate(titles):
        result = translate_one(title)
        if result == title:
            print(f"⚠️ 第{i+1}條保留原文（翻譯源均失敗）")
        else:
            print(f"✅ 第{i+1}條已翻譯")
        translated.append(result)
        time.sleep(0.8)
    return translated


# ── 關鍵詞標籤 ──────────────────────────────────────────────────
KEYWORDS = {
    "ETF": "#ETF", "Federal Reserve": "#宏观", "Fed": "#宏观",
    "inflation": "#宏观", "regulation": "#监管", "SEC": "#监管",
    "whale": "#巨鲸", "institution": "#机构", "BlackRock": "#机构",
    "Bitcoin": "#BTC", "BTC": "#BTC", "Ethereum": "#ETH", "ETH": "#ETH",
    "Solana": "#SOL", "SOL": "#SOL", "stablecoin": "#稳定币",
    "funding": "#融资", "raises": "#融资", "quantum": "#量子",
    "hack": "#安全", "exploit": "#安全",
    "比特币": "#BTC", "以太坊": "#ETH", "监管": "#监管",
    "巨鲸": "#巨鲸", "机构": "#机构", "稳定币": "#稳定币",
}

def extract_tags(title):
    tags = []
    for kw, tag in KEYWORDS.items():
        if kw.lower() in title.lower() and tag not in tags:
            tags.append(tag)
    return tags[:3]


# ── 生成新聞 HTML ────────────────────────────────────────────────
def build_news_html(items, today_str):
    if not items:
        return ""
    parts = []
    for i, item in enumerate(items[:5], 1):
        tags = extract_tags(item["title"])
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
        title = item["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        url   = item["url"].replace('"', '%22')
        time_display = item["time"] if item["time"] else today_str
        parts.append(f'''        <a class="news-card" href="{url}" target="_blank">
            <div class="news-index">{i:02d}</div>
            <div class="news-body">
                <div class="news-title">{title}</div>
                <div class="news-footer">
                    {tags_html}
                    <a class="news-link" href="{url}" target="_blank" data-i18n="read_more">查看原文 →</a>
                    <span class="news-time">{time_display} · {item["source"]}</span>
                </div>
            </div>
        </a>''')
    return "\n".join(parts)


# ── 抓取市場數據（預載解決瀏覽器 CoinGecko 限速問題）───────────
def fetch_market_data():
    import json
    data = {}

    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        resp.raise_for_status()
        data["fng"] = int(resp.json()["data"][0]["value"])
        print(f"✅ FNG: {data['fng']}")
    except Exception as e:
        print(f"⚠️ FNG 失敗: {e}")
    time.sleep(0.5)

    try:
        resp = requests.get("https://api.coingecko.com/api/v3/global", timeout=15)
        resp.raise_for_status()
        d = resp.json()["data"]
        data["cap"] = d["total_market_cap"]["usd"]
        data["capChg"] = d["market_cap_change_percentage_24h_usd"]
        print(f"✅ Market Cap: ${data['cap']/1e12:.2f}T")
    except Exception as e:
        print(f"⚠️ Market Cap 失敗: {e}")
    time.sleep(1)

    try:
        resp = requests.get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
            "?symbol=BTCUSDT&period=5m&limit=1", timeout=10)
        resp.raise_for_status()
        d = resp.json()[0]
        data["longPct"]  = f"{float(d['longAccount']) * 100:.1f}"
        data["shortPct"] = f"{float(d['shortAccount']) * 100:.1f}"
        print(f"✅ L/S: {data['longPct']}% / {data['shortPct']}%")
    except Exception as e:
        print(f"⚠️ L/S 失敗: {e}")
    time.sleep(1)

    tokens = []
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets"
            "?vs_currency=usd&ids=bitcoin,ethereum,solana"
            "&order=market_cap_desc&per_page=3&sparkline=false", timeout=15)
        resp.raise_for_status()
        for c in resp.json():
            tokens.append({"id": c["id"], "symbol": c["symbol"], "name": c["name"],
                           "current_price": c["current_price"],
                           "price_change_percentage_24h": c.get("price_change_percentage_24h", 0),
                           "type": "fixed"})
        print(f"✅ Fixed tokens: {[t['symbol'] for t in tokens]}")
    except Exception as e:
        print(f"⚠️ Fixed tokens 失敗: {e}")
    time.sleep(1)

    try:
        resp = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15)
        resp.raise_for_status()
        trend_ids = [c["item"]["id"] for c in resp.json()["coins"][:2]]
        time.sleep(1)
        resp2 = requests.get(
            f"https://api.coingecko.com/api/v3/coins/markets"
            f"?vs_currency=usd&ids={','.join(trend_ids)}&per_page=2&sparkline=false", timeout=15)
        resp2.raise_for_status()
        for c in resp2.json():
            tokens.append({"id": c["id"], "symbol": c["symbol"], "name": c["name"],
                           "current_price": c["current_price"],
                           "price_change_percentage_24h": c.get("price_change_percentage_24h", 0),
                           "type": "trending"})
        print(f"✅ All tokens: {[t['symbol'] for t in tokens]}")
    except Exception as e:
        print(f"⚠️ Trending tokens 失敗: {e}")

    if tokens:
        data["tokens"] = tokens
    return data


# ── 更新 index.html ──────────────────────────────────────────────
def update_html(news_html, market_data):
    import json
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    if news_html:
        pattern = r'(<!-- NEWS_START -->).*?(<!-- NEWS_END -->)'
        replacement = f'<!-- NEWS_START -->\n{news_html}\n        <!-- NEWS_END -->'
        content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
        if count == 0:
            print("⚠️ 找不到 NEWS 標記")
        else:
            print("✅ 新聞已更新")

    if market_data:
        preloaded = f"<script>window.PRELOADED = {json.dumps(market_data, ensure_ascii=False)};</script>"
        content, count2 = re.subn(
            r'<!-- MARKET_DATA_START -->.*?<!-- MARKET_DATA_END -->',
            f'<!-- MARKET_DATA_START -->{preloaded}<!-- MARKET_DATA_END -->',
            content, flags=re.DOTALL)
        if count2 == 0:
            print("⚠️ 找不到 MARKET_DATA 標記")
        else:
            print("✅ 市場數據已預載")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ index.html 完成（{datetime.now(TZ_TAIPEI).strftime('%Y-%m-%d %H:%M')} 台北時間）")


# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 AIU Daily Updater 開始執行...")
    today_str = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")

    news = fetch_news()
    news_html = ""
    if not news:
        print("ℹ️ 無新聞，保留舊內容")
    else:
        print(f"📰 共 {len(news[:5])} 條，開始翻譯...")
        titles_zh = translate_to_zh([item["title"] for item in news[:5]])
        for i, item in enumerate(news[:5]):
            item["title"] = titles_zh[i]
        news_html = build_news_html(news, today_str)

    print("\n📊 抓取市場數據...")
    market_data = fetch_market_data()

    update_html(news_html, market_data)
    print("🎉 完成！")
