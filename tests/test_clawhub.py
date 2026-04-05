"""Tests for fetchers/clawhub.py and reporter clawhub rendering."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock


# ── fetcher ───────────────────────────────────────────────

class TestFetchLatestSkills:
    def test_returns_list_on_success(self):
        from fetchers.clawhub import _fetch_latest_skills
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": [
            {"name": "skill-a", "displayName": "Skill A", "summary": "Does A",
             "ownerHandle": "user1", "latestVersion": "1.0.0",
             "isOfficial": False, "verificationTier": None,
             "capabilityTags": [], "updatedAt": 1234567890}
        ]}
        with patch("fetchers.clawhub.requests.get", return_value=mock_resp):
            items = _fetch_latest_skills(limit=1)
        assert len(items) == 1
        assert items[0]["name"] == "skill-a"

    def test_returns_empty_on_exception(self):
        from fetchers.clawhub import _fetch_latest_skills
        with patch("fetchers.clawhub.requests.get", side_effect=Exception("network error")):
            items = _fetch_latest_skills()
        assert items == []


class TestSearchSkills:
    def test_parses_results_key(self):
        """Search API returns {results: [{package: {...}}]}"""
        from fetchers.clawhub import _search_skills
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"results": [
            {"package": {"name": "pm-tool", "displayName": "PM Tool", "summary": "Helps PMs",
                         "ownerHandle": "u", "latestVersion": "1.0", "isOfficial": False,
                         "verificationTier": None, "capabilityTags": [], "updatedAt": 0}}
        ]}
        with patch("fetchers.clawhub.requests.get", return_value=mock_resp):
            items = _search_skills("product manager")
        assert len(items) == 1
        assert items[0]["name"] == "pm-tool"

    def test_parses_items_key(self):
        """Search API returns {items: [...]} fallback"""
        from fetchers.clawhub import _search_skills
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": [
            {"name": "fin-skill", "displayName": "Fin", "summary": "Finance",
             "ownerHandle": "u", "latestVersion": "2.0", "isOfficial": True,
             "verificationTier": "structural", "capabilityTags": ["finance"], "updatedAt": 0}
        ]}
        with patch("fetchers.clawhub.requests.get", return_value=mock_resp):
            items = _search_skills("finance")
        assert items[0]["name"] == "fin-skill"

    def test_returns_empty_on_exception(self):
        from fetchers.clawhub import _search_skills
        with patch("fetchers.clawhub.requests.get", side_effect=Exception("timeout")):
            items = _search_skills("anything")
        assert items == []


class TestSlimSkill:
    def test_slim_truncates_summary(self):
        from fetchers.clawhub import _slim_skill
        item = {
            "name": "my-skill", "displayName": "My Skill",
            "summary": "x" * 400, "ownerHandle": "u",
            "latestVersion": "1.0", "isOfficial": False,
            "verificationTier": None, "capabilityTags": [], "updatedAt": 0,
        }
        result = _slim_skill(item)
        assert len(result["summary"]) <= 300
        assert result["url"] == "https://clawhub.ai/plugins/my-skill"

    def test_slim_preserves_official_flag(self):
        from fetchers.clawhub import _slim_skill
        item = {
            "name": "official-skill", "displayName": "Official",
            "summary": "desc", "ownerHandle": "clawhub",
            "latestVersion": "1.0", "isOfficial": True,
            "verificationTier": "structural", "capabilityTags": [], "updatedAt": 0,
        }
        result = _slim_skill(item)
        assert result["isOfficial"] is True


class TestDedup:
    def test_dedup_by_name(self):
        from fetchers.clawhub import _dedup
        items = [
            {"name": "a", "displayName": "A"},
            {"name": "b", "displayName": "B"},
            {"name": "a", "displayName": "A duplicate"},
        ]
        result = _dedup(items)
        assert len(result) == 2
        assert result[0]["displayName"] == "A"

    def test_dedup_skips_empty_name(self):
        from fetchers.clawhub import _dedup
        items = [{"name": "", "displayName": "X"}, {"name": "a", "displayName": "A"}]
        result = _dedup(items)
        # empty-name items are dropped
        assert all(i["name"] != "" for i in result)


class TestFetchClawhub:
    def test_full_fetch_returns_three_keys(self):
        from fetchers import clawhub as m

        skill = {"name": "s", "displayName": "S", "summary": "desc",
                 "ownerHandle": "u", "latestVersion": "1.0", "isOfficial": False,
                 "verificationTier": None, "capabilityTags": [], "updatedAt": 0}
        with patch.object(m, "_fetch_latest_skills", return_value=[skill] * 5), \
             patch.object(m, "_search_skills", return_value=[skill]):
            result = m.fetch_clawhub()

        assert "trending" in result
        assert "pm_skills" in result
        assert "finance_skills" in result
        assert len(result["trending"]) <= 20

    def test_fetch_gracefully_handles_empty(self):
        from fetchers import clawhub as m
        with patch.object(m, "_fetch_latest_skills", return_value=[]), \
             patch.object(m, "_search_skills", return_value=[]):
            result = m.fetch_clawhub()
        assert result["trending"] == []
        assert result["pm_skills"] == []
        assert result["finance_skills"] == []


# ── reporter ──────────────────────────────────────────────

class TestClawhubTrending:
    def _good_data(self):
        return {
            "picks": [
                {"name": "awesome-skill", "displayName": "Awesome Skill",
                 "url": "https://clawhub.ai/plugins/awesome-skill",
                 "what": "技能内容描述", "why": "核心优势", "use_case": "适用场景",
                 "rating": 5, "isOfficial": False},
            ],
            "trend_summary": "AI智能体技能快速增长",
            "hot_direction": "记忆管理"
        }

    def test_renders_picks(self):
        from reporter import _clawhub_trending
        html = _clawhub_trending(self._good_data())
        assert "Awesome Skill" in html
        assert "技能内容描述" in html

    def test_renders_summary(self):
        from reporter import _clawhub_trending
        html = _clawhub_trending(self._good_data())
        assert "AI智能体技能快速增长" in html
        assert "记忆管理" in html

    def test_error_shows_message(self):
        from reporter import _clawhub_trending
        html = _clawhub_trending({"error": "API失败"})
        assert "分析失败" in html

    def test_missing_picks_no_crash(self):
        from reporter import _clawhub_trending
        html = _clawhub_trending({})
        assert html

    def test_xss_escaped(self):
        from reporter import _clawhub_trending
        data = self._good_data()
        data["picks"][0]["displayName"] = "<script>alert(1)</script>"
        html = _clawhub_trending(data)
        assert "<script>" not in html


class TestClawhubPicks:
    def _good_data(self):
        return {
            "picks": [
                {"name": "pm-copilot", "displayName": "PM Copilot",
                 "url": "https://clawhub.ai/plugins/pm-copilot",
                 "what": "需求文档生成", "why": "提升需求质量", "use_case": "需求评审",
                 "rating": 4, "isOfficial": False},
            ],
            "summary": "适合产品经理的AI技能套件"
        }

    def test_renders_picks_and_summary(self):
        from reporter import _clawhub_picks
        html = _clawhub_picks(self._good_data())
        assert "PM Copilot" in html
        assert "适合产品经理的AI技能套件" in html

    def test_empty_data_shows_na(self):
        from reporter import _clawhub_picks
        html = _clawhub_picks({})
        assert "暂无" in html

    def test_none_data_shows_na(self):
        from reporter import _clawhub_picks
        html = _clawhub_picks(None)
        assert "暂无" in html

    def test_error_shows_message(self):
        from reporter import _clawhub_picks
        html = _clawhub_picks({"error": "超时"})
        assert "分析失败" in html


class TestSkillCards:
    def test_renders_official_badge(self):
        from reporter import _skill_cards
        picks = [{"name": "s", "displayName": "My Skill", "url": "",
                  "what": "w", "why": "y", "use_case": "u",
                  "rating": 5, "isOfficial": True}]
        html = _skill_cards(picks)
        assert "官方" in html
        assert "⭐⭐⭐⭐⭐" in html

    def test_no_official_no_badge(self):
        from reporter import _skill_cards
        picks = [{"name": "s", "displayName": "My Skill", "url": "",
                  "what": "w", "why": "y", "use_case": "u",
                  "rating": 3, "isOfficial": False}]
        html = _skill_cards(picks)
        assert "官方" not in html

    def test_rating_clamped(self):
        from reporter import _skill_cards
        picks = [{"name": "s", "displayName": "D", "url": "",
                  "what": "", "why": "", "use_case": "",
                  "rating": 99, "isOfficial": False}]
        html = _skill_cards(picks)
        assert "⭐⭐⭐⭐⭐" in html

    def test_empty_picks_returns_empty(self):
        from reporter import _skill_cards
        assert _skill_cards([]) == ""


class TestRenderClawhub:
    def _make_clawhub_results(self):
        pick = {"name": "s", "displayName": "Skill", "url": "",
                "what": "w", "why": "y", "use_case": "u", "rating": 4, "isOfficial": False}
        return {
            "raw": {"trending": [], "pm_skills": [], "finance_skills": []},
            "claude": {
                "trending": {"picks": [pick], "trend_summary": "趋势", "hot_direction": "AI"},
                "pm_skills": {"picks": [], "summary": "PM推荐"},
                "finance_skills": {"picks": [], "summary": "金融推荐"},
            },
            "gpt": {"error": "超时"},
        }

    def test_render_clawhub_section(self):
        from reporter import _render_clawhub
        html = _render_clawhub(self._make_clawhub_results())
        assert "ClawHub" in html
        assert "产品经理专项技能" in html
        assert "金融行业专项技能" in html

    def test_build_report_includes_clawhub(self):
        from reporter import build_report
        from datetime import date
        results = {
            "finance": {"raw": {}, "claude": {"error": "x"}, "gpt": {"error": "x"}},
            "news":    {"raw": {}, "claude": {"error": "x"}, "gpt": {"error": "x"}},
            "ai":      {"raw": {}, "claude": {"error": "x"}, "gpt": {"error": "x"}},
            "github":  {"raw": {}, "claude": {"error": "x"}, "gpt": {"error": "x"}},
            "clawhub": self._make_clawhub_results(),
        }
        html = build_report(results, date(2026, 4, 5))
        assert "ClawHub 技能精选" in html
        assert "<html" in html
