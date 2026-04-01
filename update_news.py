#!/usr/bin/env python3
"""
AIU Daily News Updater
每天由 GitHub Actions 執行，抓取最新新聞並更新 index.html
修正：改用 RSS 靜態源 + Google Translate 翻譯為簡體中文
新增：預載市場數據（FNG、市值、多空比、代幣）解決 CoinGecko 瀏覽器限速問題
"""

import re
import json
import time
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

TZ_TAIPEI = timezone(timedelta(hours=8))

# ── RSS 新聞來源（靜態 XML，不需要 JavaScript）──────────────────
RSS_SOURCES = [
    ("https://cointelegraph.com/rss",                    "CoinTelegraph"),
    ("https://decrypt.co/feed",                          "Decrypt"),
    ("https://www.coindesk.com/arc/outboundfeeds/rss/",  "CoinDesk"),
]

def fetch_rss(url, source_name):
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AIUBot/1.0)"
        })
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        results = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=36)

        for item in items[:20]:
            title_el = item.find("title")
            link_el  = item.find("link")
            date_el  = item.find("pubDate") or item.find("published")

            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if len(title) < 10:
                continue

            link = ""
            if link_el is not None:
                link = (link_el.text or link_el.get("href") or "").strip()

            time_str = ""
            if date_el is not None and date_el.text:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_time = parsedate_to_datetime(date_el.text.strip())
                    if pub_time.replace(tzinfo=timezone.utc) < cutoff:
                        continue
                    time_str = pub_time.astimezone(TZ_TAIPEI).strftime("%H:%M")
                except Exception:
                    pass

            results.append({
                "title": title,
                "url": link,
                "time": time_str,
                "source": source_name
            })

        print(f"✅ {source_name}: 抓到 {len(results)} 條")
        return results[:8]

    except Exception as e:
        print(f"⚠️ {source_name} 抓取失敗: {e}")
        return []


def fetch_news():
    for url, name in RSS_SOURCES:
        items = fetch_rss(url, name)
        if items:
            return items
    print("❌ 所有來源均失敗，保留舊新聞")
    return []


# ── Google Translate（免費端點，逐條翻譯）───────────────────────
def translate_to_zh(titles):
    translated = []
    for title in titles:
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single"
                f"?client=gtx&sl=en&tl=zh-CN&dt=t&q={quote(title)}"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            result = "".join(part[0] for part in data[0] if part[0])
            translated.append(result.strip() if result.strip() else title)
        except Exception as e:
            print(f"⚠️ 翻譯失敗，保留原文: {e}")
            translated.append(title)
        time.sleep(0.5)
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


# ── 抓取市場數據（預載解決瀏覽器限速問題）─────────────────────
def fetch_market_data():
    data = {}

    # 恐惧贪婪指数
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        resp.raise_for_status()
        j = resp.json()
        data["fng"] = int(j["data"][0]["value"])
        print(f"✅ FNG: {data['fng']}")
    except Exception as e:
        print(f"⚠️ FNG 抓取失敗: {e}")

    time.sleep(0.5)

    # 總市值
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/global", timeout=15)
        resp.raise_for_status()
        j = resp.json()["data"]
        data["cap"] = j["total_market_cap"]["usd"]
        data["capChg"] = j["market_cap_change_percentage_24h_usd"]
        print(f"✅ Market Cap: ${data['cap']/1e12:.2f}T  {data['capChg']:+.2f}%")
    except Exception as e:
        print(f"⚠️ CoinGecko Global 抓取失敗: {e}")

    time.sleep(1)

    # BTC 多空比
    try:
        resp = requests.get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
            "?symbol=BTCUSDT&period=5m&limit=1",
            timeout=10
        )
        resp.raise_for_status()
        d = resp.json()[0]
        data["longPct"]  = f"{float(d['longAccount']) * 100:.1f}"
        data["shortPct"] = f"{float(d['shortAccount']) * 100:.1f}"
        print(f"✅ L/S: {data['longPct']}% / {data['shortPct']}%")
    except Exception as e:
        print(f"⚠️ Binance L/S 抓取失敗: {e}")

    time.sleep(1)

    # 固定代幣 BTC/ETH/SOL
    tokens = []
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets"
            "?vs_currency=usd&ids=bitcoin,ethereum,solana"
            "&order=market_cap_desc&per_page=3&sparkline=false",
            timeout=15
        )
        resp.raise_for_status()
        fixed = resp.json()
        for c in fixed:
            tokens.append({
                "id": c["id"],
                "symbol": c["symbol"],
                "name": c["name"],
                "current_price": c["current_price"],
                "price_change_percentage_24h": c.get("price_change_percentage_24h", 0),
                "type": "fixed"
            })
        print(f"✅ Fixed tokens: {[t['symbol'] for t in tokens]}")
    except Exception as e:
        print(f"⚠️ CoinGecko Fixed Tokens 抓取失敗: {e}")

    time.sleep(1)

    # 趨勢代幣 (前2名)
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            timeout=15
        )
        resp.raise_for_status()
        trend_ids = [c["item"]["id"] for c in resp.json()["coins"][:2]]
        print(f"✅ Trending IDs: {trend_ids}")

        time.sleep(1)

        ids_str = ",".join(trend_ids)
        resp2 = requests.get(
            f"https://api.coingecko.com/api/v3/coins/markets"
            f"?vs_currency=usd&ids={ids_str}&per_page=2&sparkline=false",
            timeout=15
        )
        resp2.raise_for_status()
        for c in resp2.json():
            tokens.append({
                "id": c["id"],
                "symbol": c["symbol"],
                "name": c["name"],
                "current_price": c["current_price"],
                "price_change_percentage_24h": c.get("price_change_percentage_24h", 0),
                "type": "trending"
            })
        print(f"✅ All tokens: {[t['symbol'] for t in tokens]}")
    except Exception as e:
        print(f"⚠️ CoinGecko Trending 抓取失敗: {e}")

    if tokens:
        data["tokens"] = tokens

    return data


# ── 更新 index.html ──────────────────────────────────────────────
def update_html(news_html, market_data):
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    # 更新新聞
    if news_html:
        pattern = r'(<!-- NEWS_START -->).*?(<!-- NEWS_END -->)'
        replacement = f'<!-- NEWS_START -->\n{news_html}\n        <!-- NEWS_END -->'
        content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
        if count == 0:
            print("⚠️ 找不到 NEWS_START/NEWS_END 標記")
        else:
            print("✅ 新聞已更新")

    # 更新市場數據預載
    if market_data:
        preloaded_js = f"<script>window.PRELOADED = {json.dumps(market_data, ensure_ascii=False)};</script>"
        market_pattern = r'<!-- MARKET_DATA_START -->.*?<!-- MARKET_DATA_END -->'
        market_replacement = f'<!-- MARKET_DATA_START -->{preloaded_js}<!-- MARKET_DATA_END -->'
        content, count2 = re.subn(market_pattern, market_replacement, content, flags=re.DOTALL)
        if count2 == 0:
            print("⚠️ 找不到 MARKET_DATA_START/END 標記")
        else:
            print("✅ 市場數據預載已更新")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(content)

    now = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d %H:%M")
    print(f"✅ index.html 已更新（{now} 台北時間）")
    return True


# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 AIU Daily Updater 開始執行...")
    today_str = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")

    # 抓取新聞
    news = fetch_news()
    news_html = ""
    if not news:
        print("ℹ️ 無新聞，保留舊內容")
    else:
        print(f"📰 共 {len(news[:5])} 條新聞，開始翻譯...")
        titles_en = [item["title"] for item in news[:5]]
        titles_zh = translate_to_zh(titles_en)
        for i, item in enumerate(news[:5]):
            item["title"] = titles_zh[i]
        news_html = build_news_html(news, today_str)

    # 抓取市場數據
    print("\n📊 抓取市場數據...")
    market_data = fetch_market_data()

    # 更新 HTML
    update_html(news_html, market_data)

    print("🎉 完成！")
