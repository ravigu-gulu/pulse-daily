"""GitHub Trending 抓取 + PM 专项 + 金融行业项目搜索。"""
import logging
import re

import requests
from bs4 import BeautifulSoup

from config import GITHUB_TRENDING_URL, GITHUB_TRENDING_WEEK, GITHUB_TOP_N, GITHUB_SEARCH_API

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# GitHub Search 查询关键词
GITHUB_PM_QUERIES = [
    "product+management+tool",
    "product+roadmap",
    "user+research+tool",
    "product+analytics",
]
GITHUB_FINANCE_QUERIES = [
    "banking+open+source",
    "quantitative+finance",
    "fintech+platform",
    "risk+management+finance",
]

CATEGORY_KEYWORDS = {
    "AI/ML":    ["ai","ml","llm","gpt","neural","model","diffusion","embedding","rag","inference"],
    "开发工具":  ["cli","tool","dev","editor","debug","lint","format","build","deploy","ci"],
    "安全":      ["security","exploit","pentest","vuln","hack","reverse","crypto","auth"],
    "基础设施":  ["k8s","kubernetes","docker","infra","cloud","server","proxy","gateway","db","database"],
}


def fetch_github() -> dict:
    today = _fetch_trending(GITHUB_TRENDING_URL, "today")
    week  = _fetch_trending(GITHUB_TRENDING_WEEK, "week")

    # Trending 合并去重
    seen  = set()
    trending = []
    for item in today + week:
        key = item["full_name"]
        if key not in seen:
            seen.add(key)
            trending.append(item)

    logger.info("  GitHub Trending: today=%d week=%d merged=%d",
                len(today), len(week), len(trending))

    pm_items      = _fetch_search_repos(GITHUB_PM_QUERIES,      "pm")
    finance_items = _fetch_search_repos(GITHUB_FINANCE_QUERIES, "finance")
    logger.info("  GitHub PM=%d Finance=%d", len(pm_items), len(finance_items))

    return {
        "trending": trending[:GITHUB_TOP_N],
        "pm":       pm_items,
        "finance":  finance_items,
    }


def _fetch_search_repos(queries: list, label: str) -> list:
    """用 GitHub Search API 搜索指定关键词，合并去重取前 10 条。"""
    seen, items = set(), []
    for q in queries:
        try:
            url = GITHUB_SEARCH_API.format(query=q)
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 403:
                logger.warning("  GitHub Search rate-limited (%s)", label)
                break
            resp.raise_for_status()
            for repo in resp.json().get("items", [])[:5]:
                full_name = repo.get("full_name", "")
                if full_name in seen:
                    continue
                seen.add(full_name)
                items.append({
                    "name":        repo.get("name", ""),
                    "full_name":   full_name,
                    "url":         repo.get("html_url", ""),
                    "description": (repo.get("description") or "")[:200],
                    "language":    repo.get("language") or "",
                    "stars":       repo.get("stargazers_count", 0),
                    "label":       label,
                })
        except Exception as e:
            logger.warning("  GitHub Search 失败(%s, %s): %s", label, q, e)
    return items[:10]


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
