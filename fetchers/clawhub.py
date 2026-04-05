"""从 ClawHub.ai 抓取热门技能与插件数据。"""
import logging
import requests
from config import CLAWHUB_BASE_URL, CLAWHUB_PM_QUERIES, CLAWHUB_FINANCE_QUERIES

logger = logging.getLogger(__name__)

HEADERS = {"Accept": "application/json", "User-Agent": "PulseDaily/1.0"}
TIMEOUT = 15


def _fetch_latest_skills(limit: int = 20) -> list:
    """抓取最新上架的技能列表。"""
    try:
        resp = requests.get(
            f"{CLAWHUB_BASE_URL}/packages",
            params={"family": "skill", "limit": limit},
            headers=HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        logger.warning("ClawHub 最新技能抓取失败: %s", e)
        return []


def _search_skills(query: str, limit: int = 10) -> list:
    """关键词搜索技能。"""
    try:
        resp = requests.get(
            f"{CLAWHUB_BASE_URL}/packages/search",
            params={"q": query, "family": "skill", "limit": limit},
            headers=HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # search 端点返回 {results: [{package: {...}}]} 或 {items: [...]}
        if "results" in data:
            return [r["package"] for r in data["results"] if "package" in r]
        return data.get("items", [])
    except Exception as e:
        logger.warning("ClawHub 搜索失败 (q=%s): %s", query, e)
        return []


def _search_plugins(query: str, limit: int = 10) -> list:
    """搜索插件（code-plugin / bundle-plugin）。"""
    try:
        resp = requests.get(
            f"{CLAWHUB_BASE_URL}/plugins",
            params={"q": query, "limit": limit},
            headers=HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if "results" in data:
            return [r["package"] for r in data["results"] if "package" in r]
        return data.get("items", [])
    except Exception as e:
        logger.warning("ClawHub 插件搜索失败 (q=%s): %s", query, e)
        return []


def _slim_skill(item: dict) -> dict:
    """精简单条技能/插件数据。"""
    return {
        "name": item.get("name", ""),
        "displayName": item.get("displayName", ""),
        "summary": (item.get("summary") or "")[:300],
        "ownerHandle": item.get("ownerHandle", ""),
        "latestVersion": item.get("latestVersion", ""),
        "isOfficial": item.get("isOfficial", False),
        "verificationTier": item.get("verificationTier"),
        "capabilityTags": item.get("capabilityTags", []),
        "updatedAt": item.get("updatedAt", 0),
        "url": f"https://clawhub.ai/plugins/{item.get('name', '')}",
    }


def _dedup(items: list) -> list:
    """按 name 去重，保留首次出现。"""
    seen, out = set(), []
    for item in items:
        key = item.get("name", "")
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def fetch_clawhub() -> dict:
    """
    返回结构：
    {
        "trending": [...],       # 最新/热门技能（20条）
        "pm_skills": [...],      # 产品经理相关技能
        "finance_skills": [...], # 金融行业相关技能
    }
    """
    logger.info("  [clawhub] 抓取最新技能...")
    trending_raw = _fetch_latest_skills(limit=30)

    logger.info("  [clawhub] 搜索 PM 技能...")
    pm_raw = []
    for q in CLAWHUB_PM_QUERIES:
        pm_raw.extend(_search_skills(q, limit=5))

    logger.info("  [clawhub] 搜索金融技能...")
    fin_raw = []
    for q in CLAWHUB_FINANCE_QUERIES:
        fin_raw.extend(_search_skills(q, limit=5))

    trending = [_slim_skill(i) for i in _dedup(trending_raw)][:20]
    pm       = [_slim_skill(i) for i in _dedup(pm_raw)][:10]
    finance  = [_slim_skill(i) for i in _dedup(fin_raw)][:10]

    logger.info(
        "  [clawhub] 完成: trending=%d pm=%d finance=%d",
        len(trending), len(pm), len(finance),
    )
    return {"trending": trending, "pm_skills": pm, "finance_skills": finance}
