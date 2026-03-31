#!/usr/bin/env python3
"""
AIU Daily News Updater
每天由 GitHub Actions 執行，抓取最新新聞並更新 index.html
"""

import requests
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

TZ_TAIPEI = timezone(timedelta(hours=8))

# ── 抓取新聞 ─────────────────────────────────────────────────
def fetch_news():
    sources = [
        ("https://www.theblockbeats.info/newsflash", parse_blockbeats),
        ("https://www.panewslab.com/zh/newsflash",   parse_panews),
        ("https://www.odaily.news/newsflash",         parse_odaily),
    ]
    for url, parser in sources:
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            items = parser(resp.text, url)
            if items:
                print(f"✅ 成功抓取 {len(items)} 條新聞 from {url}")
                return items
        except Exception as e:
            print(f"⚠️ 抓取失敗 {url}: {e}")
    return []

def parse_blockbeats(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for el in soup.select(".newsflash-item, .news-item, article")[:20]:
        title_el = el.select_one("h3, h2, .title, .news-title")
        time_el  = el.select_one("time, .time, .date")
        link_el  = el.select_one("a[href]")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        time_str = time_el.get_text(strip=True) if time_el else ""
        href = link_el["href"] if link_el else base_url
        if href.startswith("/"):
            href = "https://www.theblockbeats.info" + href
        items.append({"title": title, "time": time_str, "url": href, "source": "BlockBeats"})
    return items[:8]

def parse_panews(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for el in soup.select(".news-item, .flash-item, article")[:20]:
        title_el = el.select_one("h3, h2, .title")
        time_el  = el.select_one("time, .time")
        link_el  = el.select_one("a[href]")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        time_str = time_el.get_text(strip=True) if time_el else ""
        href = link_el["href"] if link_el else base_url
        if href.startswith("/"):
            href = "https://www.panewslab.com" + href
        items.append({"title": title, "time": time_str, "url": href, "source": "PANews"})
    return items[:8]

def parse_odaily(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for el in soup.select(".newsflash-item, .flash-item, article")[:20]:
        title_el = el.select_one("h3, h2, .title")
        time_el  = el.select_one("time, .time")
        link_el  = el.select_one("a[href]")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        time_str = time_el.get_text(strip=True) if time_el else ""
        href = link_el["href"] if link_el else base_url
        if href.startswith("/"):
            href = "https://www.odaily.news" + href
        items.append({"title": title, "time": time_str, "url": href, "source": "Odaily"})
    return items[:8]

# ── 生成新聞 HTML ─────────────────────────────────────────────
KEYWORDS = {
    "ETF": "#ETF", "美聯儲": "#美聯儲", "通脹": "#宏觀",
    "監管": "#監管", "巨鯨": "#巨鯨", "機構": "#機構",
    "比特幣": "#BTC", "比特币": "#BTC", "BTC": "#BTC",
    "以太坊": "#ETH", "ETH": "#ETH", "Solana": "#SOL",
    "穩定幣": "#穩定幣", "融資": "#融資", "量子": "#量子計算",
}

def extract_tags(title):
    tags = []
    for kw, tag in KEYWORDS.items():
        if kw in title and tag not in tags:
            tags.append(tag)
    return tags[:3]

def build_news_html(items):
    if not items:
        return '<div style="color:#8b949e;padding:20px;text-align:center;">暫無新聞數據 ⚠️</div>'

    html_parts = []
    for i, item in enumerate(items[:5], 1):
        tags = extract_tags(item["title"])
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
        html_parts.append(f"""
    <a class="news-card" href="{item['url']}" target="_blank">
      <div class="news-index">{i:02d}</div>
      <div class="news-body">
        <div class="news-title">{item['title']}</div>
        <div class="news-footer">
          {tags_html}
          <a class="news-link" href="{item['url']}" target="_blank">查看原文 →</a>
          <span class="news-time">{item['time']} · {item['source']}</span>
        </div>
      </div>
    </a>""")
    return "\n".join(html_parts)

# ── 更新 index.html ───────────────────────────────────────────
def update_html(news_html):
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    # 替換新聞區塊（在 news-notice div 之後到 tokens section 之前）
    new_block = (
        '<!-- news-notice -->\n'
        '  <div class="news-notice">💡 新聞每天早上 9:00 自動更新。代幣價格每 5 分鐘即時刷新。</div>\n'
        '  <div class="news-list" id="news-list">\n'
        + news_html +
        '\n  </div>'
    )

    # 用正則替換 news-notice 到 news-list 結束的區塊
    pattern = r'<!-- news-notice -->.*?</div>\s*<!-- end news -->'
    replaced = re.sub(pattern, new_block + '\n  <!-- end news -->', content, flags=re.DOTALL)

    if replaced == content:
        # 若正則沒匹配到，改用備用標記替換
        pattern2 = r'<div class="news-notice">.*?</div>\s*<div class="news-list"[^>]*>.*?</div>(?=\s*<!-- ── Top)'
        replaced = re.sub(pattern2, new_block, content, flags=re.DOTALL)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(replaced)

    now = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d %H:%M")
    print(f"✅ index.html 已更新 ({now} 台北時間)")

# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 AIU Daily Updater 開始執行...")
    news = fetch_news()
    news_html = build_news_html(news)
    update_html(news_html)
    print("🎉 完成！")
