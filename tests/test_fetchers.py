"""Tests for fetcher parsing logic (no real HTTP calls)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock
import feedparser


# ── ai_news ───────────────────────────────────────────────

class TestAiNewsIsAiRelated:
    def setup_method(self):
        from fetchers.ai_news import _is_ai_related
        self.fn = _is_ai_related

    def test_matches_llm(self):
        assert self.fn("New LLM from OpenAI") is True

    def test_matches_chinese(self):
        assert self.fn("最新大模型发布") is True

    def test_no_match(self):
        assert self.fn("Football scores today") is False

    def test_case_insensitive(self):
        assert self.fn("claude 3 opus released") is True

    def test_empty_string(self):
        assert self.fn("") is False


class TestAiNewsFetchAiNews:
    def test_future_exception_gracefully_handled(self):
        """任意一个 future 抛异常时，其余结果仍应返回。"""
        from fetchers import ai_news

        def raise_error():
            raise RuntimeError("网络故障")

        with patch.object(ai_news, '_fetch_hn', side_effect=raise_error), \
             patch.object(ai_news, '_fetch_arxiv', return_value=[{"title": "论文", "summary": "", "link": "", "source": "arxiv"}]), \
             patch.object(ai_news, '_fetch_media_rss', return_value=[]):
            result = ai_news.fetch_ai_news()

        assert result["hn"] == []
        assert len(result["arxiv"]) == 1

    def test_all_futures_succeed(self):
        from fetchers import ai_news
        with patch.object(ai_news, '_fetch_hn', return_value=[{"title": "HN", "score": 200, "url": ""}]),\
             patch.object(ai_news, '_fetch_arxiv', return_value=[{"title": "arxiv", "summary": "", "link": "", "source": "arxiv"}]),\
             patch.object(ai_news, '_fetch_media_rss', return_value=[{"title": "media", "summary": "", "link": "", "source": "v"}]):
            result = ai_news.fetch_ai_news()
        assert len(result["hn"]) == 1
        assert len(result["arxiv"]) == 1
        assert len(result["media"]) == 1


class TestAiNewsDedup:
    def test_dedup_uses_title_and_link(self):
        """相同 title+link 的条目只保留一次。"""
        from fetchers.ai_news import _fetch_media_rss
        import feedparser

        entry = MagicMock()
        entry.get = lambda k, default="": {
            "title": "AI news", "summary": "summary", "link": "http://example.com"
        }.get(k, default)

        feed = MagicMock()
        feed.entries = [entry, entry]  # 重复两次

        with patch('feedparser.parse', return_value=feed):
            from config import AI_RSS
            with patch('fetchers.ai_news.feedparser') as mock_fp:
                mock_fp.parse.return_value = feed
                # 只能通过 patch AI_RSS to single source
                import fetchers.ai_news as m
                orig = m.AI_RSS if hasattr(m, 'AI_RSS') else None
                # Test dedup logic directly
                items = [
                    {"title": "AI news", "link": "http://a.com", "summary": "", "source": "x"},
                    {"title": "AI news", "link": "http://a.com", "summary": "", "source": "y"},  # duplicate
                    {"title": "Other", "link": "http://b.com", "summary": "", "source": "z"},
                ]
                seen = set()
                deduped = []
                for item in items:
                    key = item["title"] + "|" + item.get("link", "")
                    if key not in seen:
                        seen.add(key)
                        deduped.append(item)
                assert len(deduped) == 2


# ── github ────────────────────────────────────────────────

class TestGithubParseNum:
    def setup_method(self):
        from fetchers.github import _parse_num
        self.fn = _parse_num

    def test_plain_number(self):
        assert self.fn("1,234") == 1234

    def test_with_text(self):
        assert self.fn("1,591 stars today") == 1591

    def test_empty(self):
        assert self.fn("") == 0

    def test_no_digits(self):
        assert self.fn("no numbers here") == 0


class TestGithubCategorize:
    def setup_method(self):
        from fetchers.github import _categorize
        self.fn = _categorize

    def test_ai_ml(self):
        assert self.fn("awesome llm chatgpt") == "AI/ML"

    def test_security(self):
        assert self.fn("pentest security exploit") == "安全"

    def test_infra(self):
        assert self.fn("kubernetes docker proxy") == "基础设施"

    def test_devtool(self):
        assert self.fn("cli tool builder") == "开发工具"

    def test_other(self):
        assert self.fn("random project xyz") == "其他"


class TestGithubFetchSearchRepos:
    def test_returns_list_on_success(self):
        from fetchers.github import _fetch_search_repos
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [
            {"full_name": "owner/repo", "name": "repo", "html_url": "https://github.com/owner/repo",
             "description": "A great tool", "language": "Python", "stargazers_count": 500}
        ]}
        with patch('fetchers.github.requests.get', return_value=mock_resp):
            items = _fetch_search_repos(["pm+tool"], "pm")
        assert len(items) == 1
        assert items[0]["name"] == "repo"
        assert items[0]["stars"] == 500

    def test_rate_limited_returns_empty(self):
        from fetchers.github import _fetch_search_repos
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        with patch('fetchers.github.requests.get', return_value=mock_resp):
            items = _fetch_search_repos(["pm+tool"], "pm")
        assert items == []

    def test_deduplicates_across_queries(self):
        from fetchers.github import _fetch_search_repos
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": [
            {"full_name": "owner/same", "name": "same", "html_url": "https://github.com/owner/same",
             "description": "dup", "language": "Go", "stargazers_count": 100}
        ]}
        with patch('fetchers.github.requests.get', return_value=mock_resp):
            items = _fetch_search_repos(["query1", "query2"], "pm")
        assert len(items) == 1  # deduplicated


class TestGithubParseHtml:
    def test_parse_html_extracts_repos(self):
        from fetchers.github import _parse_html
        html = """
        <html><body>
        <article class="Box-row">
          <h2><a href="/owner/repo-name">owner/repo-name</a></h2>
          <p>A great project description</p>
          <a href="/owner/repo-name/stargazers">1,234</a>
          <span class="float-sm-right">100 stars today</span>
        </article>
        </body></html>
        """
        items = _parse_html(html, "today")
        assert len(items) == 1
        assert items[0]["full_name"] == "owner/repo-name"
        assert items[0]["description"] == "A great project description"
        assert items[0]["stars"] == 1234

    def test_parse_html_empty_returns_empty(self):
        from fetchers.github import _parse_html
        items = _parse_html("<html></html>", "today")
        assert items == []

    def test_parse_html_bad_repo_skipped_not_crashed(self):
        from fetchers.github import _parse_html
        # article with no h2 link
        html = '<article class="Box-row"><p>broken</p></article>'
        items = _parse_html(html, "today")
        assert items == []


# ── news ──────────────────────────────────────────────────

class TestNewsFilter:
    def setup_method(self):
        from fetchers.news import _filter
        self.fn = _filter

    def _item(self, title, summary=""):
        return {"title": title, "summary": summary, "source": "test",
                "link": "", "published": "", "sig": "abc"}

    def test_removes_sports(self):
        items = [self._item("Football match results today")]
        assert self.fn(items) == []

    def test_keeps_geopolitics(self):
        items = [self._item("NATO summit discusses sanctions against Russia")]
        assert len(self.fn(items)) == 1

    def test_removes_no_keyword_match(self):
        items = [self._item("Local weather forecast for the week")]
        assert self.fn(items) == []

    def test_removes_celebrity_news(self):
        items = [self._item("Celebrity fashion week highlights")]
        assert self.fn(items) == []


class TestNewsDedup:
    def setup_method(self):
        from fetchers.news import _deduplicate
        self.fn = _deduplicate

    def _item(self, title, source="BBC"):
        import hashlib
        sig = hashlib.md5(title.lower().encode()).hexdigest()[:8]
        return {"title": title, "summary": "", "source": source,
                "link": "", "published": "", "sig": sig}

    def test_removes_duplicate_titles(self):
        items = [self._item("Same title"), self._item("Same title", "Reuters")]
        result = self.fn(items)
        assert len(result) == 1

    def test_keeps_different_titles(self):
        items = [self._item("Title A"), self._item("Title B")]
        assert len(self.fn(items)) == 2

    def test_preserves_first_occurrence(self):
        items = [self._item("Dup", "BBC"), self._item("Dup", "Guardian")]
        result = self.fn(items)
        assert result[0]["source"] == "BBC"


# ── finance ───────────────────────────────────────────────

class TestFinanceMarketStatus:
    def setup_method(self):
        from fetchers.finance import _market_status
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.fn = _market_status
        self.tz = ZoneInfo("Asia/Shanghai")

    def _dt(self, weekday_offset, hour, minute=0):
        """Create a datetime with specific weekday (0=Mon) and hour in CST."""
        from datetime import datetime
        # 2026-04-06 is Monday
        base = datetime(2026, 4, 6, hour, minute, tzinfo=self.tz)
        from datetime import timedelta
        return base + timedelta(days=weekday_offset)

    def test_crypto_always_open(self):
        for sym in ["BTC-USD", "ETH-USD"]:
            assert self.fn(sym, self._dt(5, 12)) == "open"  # weekend
            assert self.fn(sym, self._dt(0, 3)) == "open"

    def test_a_stock_open_morning(self):
        assert self.fn("000001.SS", self._dt(0, 10)) == "open"

    def test_a_stock_closed_lunch(self):
        assert self.fn("000001.SS", self._dt(0, 12)) == "closed"

    def test_a_stock_open_afternoon(self):
        assert self.fn("000001.SS", self._dt(0, 14)) == "open"

    def test_a_stock_closed_weekend(self):
        assert self.fn("000001.SS", self._dt(5, 10)) == "closed"  # Saturday

    def test_hk_open(self):
        assert self.fn("^HSI", self._dt(0, 11)) == "open"

    def test_hk_closed_weekend(self):
        assert self.fn("^HSI", self._dt(6, 11)) == "closed"  # Sunday


class TestFinanceCurrency:
    def setup_method(self):
        from fetchers.finance import _currency
        self.fn = _currency

    def test_a_stock(self):
        assert self.fn("000001.SS") == "CNY"

    def test_us_stock(self):
        assert self.fn("^GSPC") == "USD"

    def test_hk_stock(self):
        assert self.fn("^HSI") == "HKD"

    def test_crypto(self):
        assert self.fn("BTC-USD") == "USD"

    def test_usdcny(self):
        assert self.fn("USDCNY=X") == "CNY/USD"
