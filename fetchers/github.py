"""GitHub Trending 抓取：requests 优先，失败回退 Playwright。"""
import logging
import re

import requests
from bs4 import BeautifulSoup

from config import GITHUB_TRENDING_URL, GITHUB_TRENDING_WEEK, GITHUB_TOP_N

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

CATEGORY_KEYWORDS = {
    "AI/ML":    ["ai","ml","llm","gpt","neural","model","diffusion","embedding","rag","inference"],
    "开发工具":  ["cli","tool","dev","editor","debug","lint","format","build","deploy","ci"],
    "安全":      ["security","exploit","pentest","vuln","hack","reverse","crypto","auth"],
    "基础设施":  ["k8s","kubernetes","docker","infra","cloud","server","proxy","gateway","db","database"],
}


def fetch_github() -> dict:
    today = _fetch_trending(GITHUB_TRENDING_URL, "today")
    week  = _fetch_trending(GITHUB_TRENDING_WEEK, "week")

    # 合并去重
    seen  = set()
    items = []
    for item in today + week:
        key = item["full_name"]
        if key not in seen:
            seen.add(key)
            items.append(item)

    logger.info("  GitHub Trending: today=%d week=%d merged=%d",
                len(today), len(week), len(items))
    return {"items": items[:GITHUB_TOP_N]}


def _fetch_trending(url: str, period: str) -> list:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_html(resp.text, period)
    except Exception as e:
        logger.warning("  GitHub Trending requests 失败(%s): %s，尝试 Playwright", period, e)
        return _fetch_playwright(url, period)


def _parse_html(html: str, period: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for repo in soup.select("article.Box-row"):
        try:
            name_tag = repo.select_one("h2 a")
            if not name_tag:
                continue
            full_name = name_tag.get("href", "").strip("/")
            desc_tag  = repo.select_one("p")
            desc      = desc_tag.get_text(strip=True) if desc_tag else ""

            lang_tag  = repo.select_one("[itemprop='programmingLanguage']")
            language  = lang_tag.get_text(strip=True) if lang_tag else ""

            stars_tag = repo.select_one("a[href$='/stargazers']")
            stars_txt = stars_tag.get_text(strip=True).replace(",", "") if stars_tag else "0"
            stars     = _parse_num(stars_txt)

            today_tag = repo.select_one(".float-sm-right")
            today_txt = today_tag.get_text(strip=True) if today_tag else ""
            stars_today = _parse_num(today_txt)

            items.append({
                "full_name":   full_name,
                "name":        full_name.split("/")[-1] if "/" in full_name else full_name,
                "url":         f"https://github.com/{full_name}",
                "description": desc[:200],
                "language":    language,
                "stars":       stars,
                "stars_today": stars_today,
                "period":      period,
                "category":    _categorize(full_name + " " + desc + " " + language),
            })
        except Exception as exc:
            logger.debug("  GitHub repo 解析失败: %s", exc)
            continue
    return items


def _fetch_playwright(url: str, period: str) -> list:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br  = pw.chromium.launch(headless=True)
            ctx = br.new_context(user_agent=HEADERS["User-Agent"])
            pg  = ctx.new_page()
            pg.goto(url, wait_until="networkidle", timeout=30_000)
            html = pg.content()
            ctx.close()
            br.close()
        return _parse_html(html, period)
    except Exception as e:
        logger.error("  GitHub Playwright 也失败(%s): %s", period, e)
        return []


def _parse_num(text: str) -> int:
    m = re.search(r"[\d,]+", text.replace(",", ""))
    return int(m.group().replace(",", "")) if m else 0


def _categorize(text: str) -> str:
    text_l = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_l for kw in keywords):
            return cat
    return "其他"
