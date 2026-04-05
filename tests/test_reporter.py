"""Tests for reporter rendering functions."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from reporter import _safe_int, _e, _fmt_price, _finance_analysis, _news_analysis, _ai_analysis, _github_analysis, build_report
from datetime import date


class TestSafeInt:
    def test_normal_int(self):
        assert _safe_int(3) == 3

    def test_string_int(self):
        assert _safe_int("5") == 5

    def test_invalid_string(self):
        assert _safe_int("bad") == 0
        assert _safe_int("bad", default=3) == 3

    def test_none(self):
        assert _safe_int(None, default=2) == 2

    def test_float_truncates(self):
        assert _safe_int(4.9) == 4


class TestEscape:
    def test_html_escape(self):
        assert "&amp;" in _e("&")
        assert "&lt;" in _e("<")
        assert "&gt;" in _e(">")
        assert "&quot;" in _e('"')

    def test_non_string_coerced(self):
        assert _e(42) == "42"
        assert _e(None) == "None"


class TestFmtPrice:
    def test_usd(self):
        assert _fmt_price(1234.5, "USD") == "$1,234.50"

    def test_cny(self):
        assert _fmt_price(3000.0, "CNY") == "3,000.00"

    def test_hkd(self):
        assert _fmt_price(25000.0, "HKD") == "HK$25,000.00"

    def test_unknown_currency(self):
        result = _fmt_price(1.2345, "XYZ")
        assert "1.2345" in result


class TestFinanceAnalysis:
    def _good_data(self):
        return {
            "market_signals": ["信号A", "信号B"],
            "gold_commodities": "黄金上涨2%",
            "china_market": "A股小幅下跌",
            "investment_advice": {
                "short_term": "短期观望",
                "mid_term": "中期布局",
                "long_term": "长期持有"
            },
            "risk_warning": "注意地缘风险",
            "watch_tomorrow": "关注非农数据"
        }

    def test_renders_signals(self):
        html = _finance_analysis(self._good_data(), "claude")
        assert "信号A" in html
        assert "信号B" in html

    def test_renders_advice(self):
        html = _finance_analysis(self._good_data(), "claude")
        assert "短期观望" in html
        assert "中期布局" in html
        assert "长期持有" in html

    def test_renders_risk(self):
        html = _finance_analysis(self._good_data(), "claude")
        assert "注意地缘风险" in html

    def test_error_shows_message(self):
        html = _finance_analysis({"error": "模型超时"}, "claude")
        assert "分析失败" in html
        assert "模型超时" in html

    def test_invalid_rating_doesnt_crash(self):
        """LLM 返回非数字 rating 时不应崩溃"""
        data = self._good_data()
        # finance analysis 不含 rating，确认不崩溃
        html = _finance_analysis(data, "claude")
        assert html  # 只要不抛异常

    def test_missing_fields_dont_crash(self):
        html = _finance_analysis({}, "claude")
        assert html  # 空 dict，不崩溃，不含 error key


class TestNewsAnalysis:
    def _good_data(self):
        return {
            "top_events": [
                {"title": "战争事件", "analysis": "分析文字", "sources": ["BBC"], "impact_level": "高"},
                {"title": "外交会议", "analysis": "会议分析", "sources": ["UN", "Guardian"], "impact_level": "中"},
            ],
            "overall_summary": "全球局势动荡",
            "china_asia_impact": "对亚太影响有限",
            "watch_next": "明日关注G7峰会"
        }

    def test_renders_events(self):
        html = _news_analysis(self._good_data())
        assert "战争事件" in html
        assert "外交会议" in html

    def test_renders_summary(self):
        html = _news_analysis(self._good_data())
        assert "全球局势动荡" in html

    def test_renders_impact(self):
        html = _news_analysis(self._good_data())
        assert "对亚太影响有限" in html

    def test_error_shows_message(self):
        html = _news_analysis({"error": "抓取失败"})
        assert "分析失败" in html

    def test_empty_events_list(self):
        data = self._good_data()
        data["top_events"] = []
        html = _news_analysis(data)
        assert "全球局势动荡" in html  # summary 仍渲染

    def test_sources_joined(self):
        html = _news_analysis(self._good_data())
        assert "UN" in html
        assert "Guardian" in html

    def test_missing_fields_dont_crash(self):
        html = _news_analysis({})
        assert html

    def test_xss_escaped(self):
        data = self._good_data()
        data["top_events"][0]["title"] = "<script>alert(1)</script>"
        html = _news_analysis(data)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestAiAnalysis:
    def _good_data(self):
        return {
            "model_updates": [
                {"name": "GPT-5", "update": "正式发布", "significance": "高"},
                {"name": "Gemini 2", "update": "多模态增强", "significance": "中"},
            ],
            "research_highlights": [
                {"title": "新型注意力机制", "plain_summary": "提升效率50%", "source": "arxiv"},
            ],
            "industry_moves": ["OpenAI 融资完成", "Anthropic 扩大团队"],
            "trend_judgment": "大模型竞争白热化"
        }

    def test_renders_model_updates(self):
        html = _ai_analysis(self._good_data())
        assert "GPT-5" in html
        assert "正式发布" in html

    def test_renders_research(self):
        html = _ai_analysis(self._good_data())
        assert "新型注意力机制" in html
        assert "提升效率50%" in html

    def test_renders_industry(self):
        html = _ai_analysis(self._good_data())
        assert "OpenAI 融资完成" in html

    def test_renders_trend(self):
        html = _ai_analysis(self._good_data())
        assert "大模型竞争白热化" in html

    def test_empty_updates_shows_na(self):
        data = self._good_data()
        data["model_updates"] = []
        html = _ai_analysis(data)
        assert "暂无" in html

    def test_error_shows_message(self):
        html = _ai_analysis({"error": "超时"})
        assert "分析失败" in html

    def test_missing_fields_dont_crash(self):
        html = _ai_analysis({})
        assert html


class TestGithubAnalysis:
    def _good_data(self):
        return {
            "picks": [
                {"name": "awesome-llm", "url": "https://github.com/a/awesome-llm",
                 "description": "LLM 工具集合", "use_case": "AI开发",
                 "stars_today": 500, "rating": 5, "category": "AI/ML"},
                {"name": "fast-api-tool", "url": "https://github.com/b/fast-api-tool",
                 "description": "API 开发工具", "use_case": "后端开发",
                 "stars_today": 200, "rating": 3, "category": "开发工具"},
            ],
            "trend_summary": "AI 工具热度持续",
            "hot_direction": "RAG 框架"
        }

    def test_renders_picks(self):
        html = _github_analysis(self._good_data())
        assert "awesome-llm" in html
        assert "LLM 工具集合" in html

    def test_renders_trend(self):
        html = _github_analysis(self._good_data())
        assert "AI 工具热度持续" in html

    def test_renders_hot_direction(self):
        html = _github_analysis(self._good_data())
        assert "RAG 框架" in html

    def test_invalid_rating_string_doesnt_crash(self):
        data = self._good_data()
        data["picks"][0]["rating"] = "excellent"  # 非数字
        html = _github_analysis(data)
        assert html  # 不崩溃
        assert "⭐" in html

    def test_rating_clamped_to_1_5(self):
        data = self._good_data()
        data["picks"][0]["rating"] = 99
        html = _github_analysis(data)
        assert "⭐⭐⭐⭐⭐" in html  # 最多5颗

    def test_missing_rating_uses_default(self):
        data = self._good_data()
        del data["picks"][0]["rating"]
        html = _github_analysis(data)
        assert "⭐" in html

    def test_error_shows_message(self):
        html = _github_analysis({"error": "模型异常"})
        assert "分析失败" in html

    def test_xss_escaped_in_url(self):
        data = self._good_data()
        data["picks"][0]["name"] = '<img src=x onerror=alert(1)>'
        html = _github_analysis(data)
        assert "<img" not in html


class TestBuildReport:
    def _make_results(self):
        return {
            "finance": {
                "raw": {"tickers": {}, "groups": {}, "snapshot_time": "2026-04-05 07:00 CST"},
                "claude": {
                    "market_signals": ["信号"], "gold_commodities": "黄金平稳",
                    "china_market": "A股稳定", "investment_advice": {"short_term": "观望"},
                    "risk_warning": "无", "watch_tomorrow": "CPI"
                },
                "gpt": {"error": "超时"},
            },
            "news": {
                "raw": {"total_raw": 10, "after_dedup": 8, "after_filter": 5, "items": []},
                "claude": {
                    "top_events": [{"title": "事件", "analysis": "分析", "sources": ["BBC"], "impact_level": "高"}],
                    "overall_summary": "综评", "china_asia_impact": "影响", "watch_next": "关注"
                },
                "gpt": {"error": "超时"},
            },
            "ai": {
                "raw": {"hn": [], "arxiv": [], "media": []},
                "claude": {
                    "model_updates": [], "research_highlights": [],
                    "industry_moves": [], "trend_judgment": "AI发展"
                },
                "gpt": {"error": "超时"},
            },
            "github": {
                "raw": {"items": []},
                "claude": {"picks": [], "trend_summary": "趋势", "hot_direction": "AI"},
                "gpt": {"error": "超时"},
            },
        }

    def test_build_report_returns_html(self):
        html = build_report(self._make_results(), date(2026, 4, 5))
        assert "<html" in html
        assert "PulseDaily" in html

    def test_build_report_contains_all_sections(self):
        html = build_report(self._make_results(), date(2026, 4, 5))
        assert "每日财经分析" in html
        assert "国际重要局势" in html
        assert "每日 AI 进展" in html
        assert "GitHub 开源精选" in html

    def test_build_report_date_shown(self):
        html = build_report(self._make_results(), date(2026, 4, 5))
        assert "2026" in html

    def test_error_module_shows_gracefully(self):
        results = self._make_results()
        results["finance"]["claude"] = {"error": "模型分析失败"}
        html = build_report(results, date(2026, 4, 5))
        assert "分析失败" in html
        assert "<html" in html  # 整体不崩溃

    def test_all_error_modules_no_crash(self):
        results = {mod: {"raw": {}, "claude": {"error": "x"}, "gpt": {"error": "x"}}
                   for mod in ["finance", "news", "ai", "github"]}
        html = build_report(results, date(2026, 4, 5))
        assert "<html" in html
