"""PulseDaily 全局配置。"""
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR    = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
TZ_CST = ZoneInfo("Asia/Shanghai")

# ── AI 模型 ───────────────────────────────────────────────
CLAUDE_MODEL = "claude-opus-4-6"
# ── 超时（秒） ────────────────────────────────────────────
TIMEOUT_MODEL  = 90    # 单次模型调用
TIMEOUT_MODULE = 180   # 单模块总时间
TIMEOUT_GLOBAL = 720   # 全局总时间

# ── 财经 tickers ──────────────────────────────────────────
TICKERS = {
    # 美股
    "^GSPC":     "标普500",
    "^IXIC":     "纳斯达克",
    "^DJI":      "道琼斯",
    # A股
    "000001.SS": "上证综指",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000688.SS": "科创板指",
    # 港股
    "^HSI":      "恒生指数",
    # 黄金/大宗
    "GC=F":      "黄金期货",
    "SI=F":      "白银期货",
    "HG=F":      "铜期货",
    "CL=F":      "WTI原油",
    # 汇率
    "DX-Y.NYB":  "美元指数",
    "USDCNY=X":  "人民币/美元",
    "EURUSD=X":  "欧元/美元",
    # 加密
    "BTC-USD":   "比特币",
    "ETH-USD":   "以太坊",
}

# ── 新闻 RSS ──────────────────────────────────────────────
NEWS_RSS = [
    ("BBC",       "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Guardian",  "https://www.theguardian.com/world/rss"),
    ("AlJazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("UN",        "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
]
NEWS_FILTER_KEYWORDS = [
    "war","sanctions","diplomacy","summit","treaty","crisis","nuclear",
    "election","missile","attack","conflict","ceasefire","negotiations",
    "G7","G20","NATO","UN","president","prime minister","minister",
    "战争","制裁","外交","峰会","协议","危机","核","选举",
]
NEWS_SKIP_KEYWORDS = [
    "sport","football","soccer","cricket","tennis","golf","nba","nfl",
    "celebrity","entertainment","fashion","lifestyle","recipe","travel tips",
]

# ── AI 新闻 RSS ───────────────────────────────────────────
AI_RSS = [
    ("TheVerge",     "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("VentureBeat",  "https://venturebeat.com/category/ai/feed/"),
    ("36kr",         "https://36kr.com/feed"),
    ("机器之心",      "https://www.jiqizhixin.com/rss"),
]
HN_API_URL   = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL  = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_MIN_SCORE = 100
AI_KEYWORDS  = [
    "AI","LLM","GPT","Claude","Gemini","Llama","Mistral","OpenAI",
    "Anthropic","DeepMind","machine learning","neural","transformer",
    "人工智能","大模型","语言模型",
]
# arxiv API v1 (Atom/XML) — works on weekends unlike RSS which returns 0 on Sat/Sun
ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL"]
ARXIV_API_URL = (
    "https://export.arxiv.org/api/query"
    "?search_query={cat}&start=0&max_results=10"
    "&sortBy=submittedDate&sortOrder=descending"
)

# ── ClawHub.ai ────────────────────────────────────────────
CLAWHUB_BASE_URL = "https://clawhub.ai/api/v1"
CLAWHUB_PM_QUERIES = [
    "product manager", "product roadmap", "user research",
    "product analytics", "requirement", "PRD",
]
CLAWHUB_FINANCE_QUERIES = [
    "finance", "trading", "investment", "bank", "quantitative",
    "fintech", "stock", "risk",
]

# ── GitHub Trending ───────────────────────────────────────
GITHUB_TRENDING_URL  = "https://github.com/trending"
GITHUB_TRENDING_WEEK = "https://github.com/trending?since=weekly"
GITHUB_TOP_N = 25
GITHUB_SEARCH_API = (
    "https://api.github.com/search/repositories"
    "?q={query}&sort=stars&order=desc&per_page=5"
)
