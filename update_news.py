#!/usr/bin/env python3
"""
AIU Daily News Updater
每天由 GitHub Actions 執行，抓取最新新聞並更新 index.html
"""

import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

TZ_TAIPEI = timezone(timedelta(hours=8))

# ── 抓取新聞 ─────────────────────────────────────────────────
def fetch_news():
    sources = [
        ("https://www.theblockbeats.info/newsflash", parse_blockbeats, "BlockBeats"),
        ("https://www.panewslab.com/zh/newsflash",   parse_generic,   "PANews"),
        ("https://www.odaily.news/newsflash",         parse_generic,   "Odaily"),
    ]
    for url, parser, name in sources:
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            items = parser(resp.text, url, name)
            if items:
                print(f"✅ 成功抓取 {len(items)} 條新聞 from {name}")
                return items
        except Exception as e:
            print(f"⚠️ 抓取失敗 {name}: {e}")
    print("❌ 所有來源均抓取失敗，保留舊新聞")
    return []

def parse_blockbeats(html, base_url, source):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for el in soup.select(".newsflash-item, .news-item, article")[:20]:
        title_el = el.select_one("h3, h2, .title, .news-title")
        time_el  = el.select_one("time, .time, .date")
        link_el  = el.select_one("a[href]")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if len(title) < 5:
            continue
        time_str = time_el.get_text(strip=True) if time_el else ""
        href = link_el["href"] if link_el else base_url
        if href.startswith("/"):
            href = "https://www.theblockbeats.info" + href
        items.append({"title": title, "time": time_str, "url": href, "source": source})
    return items[:8]

def parse_generic(html, base_url, source):
    soup = BeautifulSoup(html, "html.parser")
    domain = base_url.split("/")[2]
    items = []
    for el in soup.select(".news-item, .flash-item, .newsflash-item, article")[:20]:
        title_el = el.select_one("h3, h2, .title")
        time_el  = el.select_one("time, .time")
        link_el  = el.select_one("a[href]")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if len(title) < 5:
            continue
        time_str = time_el.get_text(strip=True) if time_el else ""
        href = link_el["href"] if link_el else base_url
        if href.startswith("/"):
            href = f"https://{domain}" + href
        items.append({"title": title, "time": time_str, "url": href, "source": source})
    return items[:8]

# ── 關鍵詞標籤 ────────────────────────────────────────────────
KEYWORDS = {
    "ETF": "#ETF", "美聯儲": "#美聯儲", "美联储": "#美联储",
    "通脹": "#宏觀", "通胀": "#宏观", "監管": "#監管", "监管": "#监管",
    "巨鯨": "#巨鯨", "巨鲸": "#巨鲸", "機構": "#機構", "机构": "#机构",
    "比特幣": "#BTC", "比特币": "#BTC", "BTC": "#BTC",
    "以太坊": "#ETH", "ETH": "#ETH", "Solana": "#SOL", "SOL": "#SOL",
    "穩定幣": "#穩定幣", "稳定币": "#稳定币",
    "融資": "#融資", "融资": "#融资", "量子": "#量子",
}

def extract_tags(title):
    tags = []
    for kw, tag in KEYWORDS.items():
        if kw in title and tag not in tags:
            tags.append(tag)
    return tags[:3]

# ── 生成新聞 HTML ─────────────────────────────────────────────
def build_news_html(items, today_str):
    if not items:
        return ""   # 返回空字串，保留舊內容

    parts = []
    for i, item in enumerate(items[:5], 1):
        tags = extract_tags(item["title"])
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
        # 轉義 HTML 特殊字符
        title = item["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        url   = item["url"].replace('"', '%22')
        time_display = item["time"] if item["time"] else today_str
        parts.append(f'''    <a class="news-card" href="{url}" target="_blank">
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

# ── 更新 index.html ───────────────────────────────────────────
def update_html(news_html):
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    # 用 <!-- NEWS_START --> 和 <!-- NEWS_END --> 精準定位並替換
    pattern = r'(<!-- NEWS_START -->).*?(<!-- NEWS_END -->)'
    replacement = f'<!-- NEWS_START -->\n{news_html}\n    <!-- NEWS_END -->'
    new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

    if count == 0:
        print("⚠️ 找不到 NEWS_START/NEWS_END 標記，跳過更新")
        return False

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_content)

    now = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d %H:%M")
    print(f"✅ index.html 新聞區塊已更新 ({now} 台北時間)")
    return True

# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 AIU Daily Updater 開始執行...")
    today_str = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")
    news = fetch_news()
    if news:
        news_html = build_news_html(news, today_str)
        update_html(news_html)
    else:
        print("ℹ️  無新聞數據，index.html 保持不變")
    print("🎉 完成！")
