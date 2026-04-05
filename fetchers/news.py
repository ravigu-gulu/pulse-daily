"""国际新闻 RSS 抓取 + 去重过滤。"""
import hashlib
import logging

import feedparser

from config import NEWS_RSS, NEWS_FILTER_KEYWORDS, NEWS_SKIP_KEYWORDS

logger = logging.getLogger(__name__)


def fetch_news() -> dict:
    """返回过滤去重后的新闻列表。"""
    raw = []
    for source, url in NEWS_RSS:
        try:
            items = _parse_rss(source, url)
            raw.extend(items)
            logger.info("  新闻[%s]: %d 条", source, len(items))
        except Exception as e:
            logger.warning("  新闻[%s] 失败: %s", source, e)

    deduped   = _deduplicate(raw)
    filtered  = _filter(deduped)
    prioritized = _prioritize(filtered)

    return {
        "items": prioritized[:40],
        "total_raw": len(raw),
        "after_dedup": len(deduped),
        "after_filter": len(filtered),
    }


def _parse_rss(source: str, url: str) -> list:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:20]:
        title   = entry.get("title", "").strip()
        summary = entry.get("summary", entry.get("description", "")).strip()
        link    = entry.get("link", "")
        pub     = entry.get("published", "")
        items.append({
            "source":  source,
            "title":   title,
            "summary": summary[:300],
            "link":    link,
            "published": pub,
            "sig":     _sig(title),
        })
    return items


def _sig(text: str) -> str:
    """标题指纹（用于去重）。"""
    normalized = " ".join(text.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()[:8]


def _deduplicate(items: list) -> list:
    """基于标题 fingerprint 去重，按进入顺序保留第一条。"""
    seen = {}
    for item in items:
        sig = item["sig"]
        if sig not in seen:
            seen[sig] = item
        else:
            # 保留来源列表
            existing = seen[sig]
            if item["source"] not in existing.get("sources_list", [existing["source"]]):
                existing.setdefault("sources_list", [existing["source"]]).append(item["source"])
    return list(seen.values())


def _filter(items: list) -> list:
    """过滤娱乐/体育；要求至少命中一个 include 关键词才保留。"""
    result = []
    for item in items:
        text = (item["title"] + " " + item["summary"]).lower()
        if any(kw.lower() in text for kw in NEWS_SKIP_KEYWORDS):
            continue
        if not any(kw.lower() in text for kw in NEWS_FILTER_KEYWORDS):
            continue
        result.append(item)
    return result


def _prioritize(items: list) -> list:
    """关键词优先排序。"""
    def score(item):
        text = (item["title"] + " " + item["summary"]).lower()
        return sum(1 for kw in NEWS_FILTER_KEYWORDS if kw.lower() in text)
    return sorted(items, key=score, reverse=True)
