"""AI 进展抓取：HN API + arxiv API v1 + 科技媒体 RSS。"""
import logging
import concurrent.futures
import xml.etree.ElementTree as ET

import feedparser
import requests

from config import (AI_RSS, HN_API_URL, HN_ITEM_URL, HN_MIN_SCORE,
                    AI_KEYWORDS, ARXIV_CATEGORIES, ARXIV_API_URL, TZ_CST)

logger = logging.getLogger(__name__)


def fetch_ai_news() -> dict:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_hn     = ex.submit(_fetch_hn)
        f_arxiv  = ex.submit(_fetch_arxiv)
        f_media  = ex.submit(_fetch_media_rss)

    try:
        hn_items = f_hn.result()
    except Exception as e:
        logger.warning("HN future 异常: %s", e)
        hn_items = []
    try:
        arxiv_items = f_arxiv.result()
    except Exception as e:
        logger.warning("arxiv future 异常: %s", e)
        arxiv_items = []
    try:
        media_items = f_media.result()
    except Exception as e:
        logger.warning("media future 异常: %s", e)
        media_items = []

    logger.info("  AI新闻: HN=%d arxiv=%d media=%d",
                len(hn_items), len(arxiv_items), len(media_items))
    return {
        "hn":     hn_items,
        "arxiv":  arxiv_items,
        "media":  media_items,
    }


def _fetch_hn() -> list:
    try:
        top_ids = requests.get(HN_API_URL, timeout=10).json()[:200]
    except Exception as e:
        logger.warning("HN top stories 失败: %s", e)
        return []

    items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_hn_item, i): i for i in top_ids}
        for f in concurrent.futures.as_completed(futures):
            item = f.result()
            if item:
                items.append(item)

    # 过滤 AI 相关且 score 足够高
    filtered = [i for i in items
                if i["score"] >= HN_MIN_SCORE and _is_ai_related(i["title"])]
    return sorted(filtered, key=lambda x: x["score"], reverse=True)[:15]


def _fetch_hn_item(item_id: int):
    try:
        data = requests.get(HN_ITEM_URL.format(item_id), timeout=8).json()
        if data.get("type") != "story" or not data.get("title"):
            return None
        return {
            "id":    item_id,
            "title": data.get("title", ""),
            "url":   data.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
            "score": data.get("score", 0),
            "comments": data.get("descendants", 0),
        }
    except Exception:
        return None


def _fetch_arxiv() -> list:
    """使用 arxiv API v1 (Atom/XML)，周末也能返回最新论文。"""
    NS = "http://www.w3.org/2005/Atom"
    items = []
    seen_ids = set()
    for cat in ARXIV_CATEGORIES:
        url = ARXIV_API_URL.format(cat=f"cat:{cat}")
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            for entry in root.findall(f"{{{NS}}}entry"):
                arxiv_id = (entry.findtext(f"{{{NS}}}id") or "").strip()
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)
                title   = (entry.findtext(f"{{{NS}}}title") or "").replace("\n", " ").strip()
                summary = (entry.findtext(f"{{{NS}}}summary") or "").replace("\n", " ").strip()[:400]
                items.append({
                    "title":   title,
                    "summary": summary,
                    "link":    arxiv_id,
                    "source":  "arxiv",
                })
        except Exception as e:
            logger.warning("arxiv API 失败 %s: %s", cat, e)
    return items[:15]


def _fetch_media_rss() -> list:
    items = []
    for source, url in AI_RSS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:300]
                if not _is_ai_related(title + " " + summary):
                    continue
                items.append({
                    "title":   title,
                    "summary": summary,
                    "link":    entry.get("link", ""),
                    "source":  source,
                })
        except Exception as e:
            logger.warning("AI媒体RSS[%s] 失败: %s", source, e)
    # 去重
    seen = set()
    deduped = []
    for item in items:
        key = item["title"] + "|" + item.get("link", "")
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:20]


def _is_ai_related(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in AI_KEYWORDS)
