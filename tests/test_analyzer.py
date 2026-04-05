"""Tests for analyzer._extract_json and _build_prompt."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analyzer import _extract_json, _build_prompt


class TestExtractJson:
    def test_simple_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_returns_none_on_empty(self):
        assert _extract_json("") is None
        assert _extract_json(None) is None

    def test_returns_none_on_no_json(self):
        assert _extract_json("just plain text") is None

    def test_json_in_markdown_code_block(self):
        text = '```json\n{"key": "value", "num": 42}\n```'
        assert _extract_json(text) == {"key": "value", "num": 42}

    def test_json_with_header_noise(self):
        """codex exec 输出格式：首行 JSON + 元信息"""
        text = (
            '{"answer": "ok"}\n'
            "Reading additional input from stdin...\n"
            "OpenAI Codex v0.118.0\n"
            "user\n"
            'some prompt {"nested": 1}\n'
            "codex\n"
            '{"answer": "ok"}\n'
            "tokens used\n1,234\n"
        )
        result = _extract_json(text)
        # 最大的 JSON 是外层 {"answer":"ok"}（它们都一样大，取第一个也 OK）
        assert result is not None
        assert result.get("answer") == "ok"

    def test_returns_largest_json_not_nested(self):
        """关键：嵌套 JSON 时应返回外层完整对象，而不是最后一个子对象"""
        outer = {
            "top_events": [
                {"title": "事件A", "analysis": "分析", "sources": ["BBC"], "impact_level": "高"},
                {"title": "事件B", "analysis": "分析B", "sources": ["UN"], "impact_level": "中"},
            ],
            "overall_summary": "综合来看局势紧张",
            "china_asia_impact": "对中国影响较小",
            "watch_next": "明日关注美联储"
        }
        text = json.dumps(outer, ensure_ascii=False)
        result = _extract_json(text)
        assert result is not None
        assert "top_events" in result
        assert "overall_summary" in result
        assert len(result["top_events"]) == 2

    def test_nested_finance_schema(self):
        outer = {
            "market_signals": ["信号1", "信号2"],
            "gold_commodities": "黄金上涨",
            "china_market": "A股下跌",
            "investment_advice": {
                "short_term": "短期观望",
                "mid_term": "中期布局",
                "long_term": "长期持有"
            },
            "risk_warning": "注意风险",
            "watch_tomorrow": "关注CPI"
        }
        text = "```json\n" + json.dumps(outer, ensure_ascii=False) + "\n```"
        result = _extract_json(text)
        assert result is not None
        assert "market_signals" in result
        assert "investment_advice" in result
        assert result["investment_advice"]["short_term"] == "短期观望"

    def test_nested_github_schema(self):
        outer = {
            "picks": [
                {"name": "repo1", "url": "https://github.com/a/b",
                 "description": "desc", "use_case": "use", "stars_today": 100,
                 "rating": 4, "category": "AI/ML"},
            ],
            "trend_summary": "AI 趋势强劲",
            "hot_direction": "大模型"
        }
        text = json.dumps(outer)
        result = _extract_json(text)
        assert "picks" in result
        assert "trend_summary" in result

    def test_nested_ai_schema(self):
        outer = {
            "model_updates": [{"name": "GPT-5", "update": "发布", "significance": "高"}],
            "research_highlights": [{"title": "论文", "plain_summary": "摘要", "source": "arxiv"}],
            "industry_moves": ["动态1"],
            "trend_judgment": "AI 高速发展"
        }
        text = json.dumps(outer, ensure_ascii=False)
        result = _extract_json(text)
        assert "model_updates" in result
        assert "trend_judgment" in result

    def test_invalid_json_ignored(self):
        text = '{invalid} {"valid": true}'
        result = _extract_json(text)
        assert result == {"valid": True}

    def test_escaped_quotes_in_string(self):
        text = '{"msg": "he said \\"hello\\""}'
        result = _extract_json(text)
        assert result == {"msg": 'he said "hello"'}

    def test_unicode_content(self):
        text = '{"title": "人工智能", "count": 42}'
        assert _extract_json(text) == {"title": "人工智能", "count": 42}


class TestBuildPrompt:
    def test_finance_prompt_contains_data(self):
        data = {"tickers": {"^GSPC": {"price": 5000}}}
        prompt = _build_prompt("finance", data)
        assert "5000" in prompt
        assert "财经分析师" in prompt

    def test_news_prompt_contains_data(self):
        data = {"items": [{"title": "Big News", "summary": "details"}]}
        prompt = _build_prompt("news", data)
        assert "Big News" in prompt
        assert "时事分析师" in prompt

    def test_ai_prompt_contains_data(self):
        data = {"hn": [], "arxiv": [{"title": "LLM paper"}], "media": []}
        prompt = _build_prompt("ai", data)
        assert "LLM paper" in prompt
        assert "AI领域" in prompt

    def test_github_prompt_contains_data(self):
        data = {"items": [{"name": "cool-repo", "stars_today": 500}]}
        prompt = _build_prompt("github", data)
        assert "cool-repo" in prompt
        assert "开源社区" in prompt

    def test_news_data_trimmed_to_fit(self):
        """news 有 40 条大数据时 prompt 不超过 7000 字符"""
        data = {
            "items": [{"title": f"News {i}", "summary": "x" * 300,
                       "source": "BBC", "link": "", "sig": "abc", "published": ""}
                      for i in range(40)],
            "total_raw": 40, "after_dedup": 40, "after_filter": 40,
        }
        prompt = _build_prompt("news", data)
        assert len(prompt) < 7000

    def test_ai_data_trimmed_to_fit(self):
        """ai 模块大数据时 prompt 不超过 7000 字符"""
        data = {
            "hn": [{"title": f"HN {i}", "score": 200, "url": ""} for i in range(15)],
            "arxiv": [{"title": f"Paper {i}", "summary": "y" * 400, "link": "", "source": "arxiv"} for i in range(15)],
            "media": [{"title": f"Media {i}", "summary": "z" * 300, "link": "", "source": "v"} for i in range(10)],
        }
        prompt = _build_prompt("ai", data)
        assert len(prompt) < 7000

    def test_trim_news_keeps_top_20(self):
        from analyzer import _trim_data
        data = {"items": [{"title": f"t{i}", "summary": "s", "source": "BBC",
                           "link": "", "sig": "x", "published": ""} for i in range(40)],
                "total_raw": 40}
        trimmed = _trim_data("news", data)
        assert len(trimmed["items"]) == 20

    def test_trim_news_strips_internal_fields(self):
        from analyzer import _trim_data
        data = {"items": [{"title": "t", "summary": "s" * 200, "source": "BBC",
                           "sig": "SECRET", "published": "2026-04-05", "link": "http://x"}],
                "total_raw": 1}
        trimmed = _trim_data("news", data)
        item = trimmed["items"][0]
        assert "sig" not in item
        assert "published" not in item
        assert len(item["summary"]) <= 150

    def test_trim_ai_limits_each_source(self):
        from analyzer import _trim_data
        data = {
            "hn": [{"title": f"h{i}", "score": i, "url": ""} for i in range(15)],
            "arxiv": [{"title": f"a{i}", "summary": "x" * 400, "link": ""} for i in range(15)],
            "media": [{"title": f"m{i}", "summary": "y" * 300, "link": "", "source": "v"} for i in range(12)],
        }
        trimmed = _trim_data("ai", data)
        assert len(trimmed["hn"]) == 10
        assert len(trimmed["arxiv"]) == 10
        assert len(trimmed["media"]) == 10

    def test_trim_finance_unchanged(self):
        from analyzer import _trim_data
        data = {"tickers": {"^GSPC": {"price": 5000}}, "groups": {}}
        assert _trim_data("finance", data) == data

    def test_long_data_fallback_truncation(self):
        """极端情况下保底截断不破坏调用"""
        data = {"items": [{"title": "x" * 500, "summary": "y" * 500, "source": "s",
                           "link": "", "sig": "z", "published": ""}] * 100}
        prompt = _build_prompt("news", data)
        assert len(prompt) < 12000

    def test_unknown_module_returns_empty_template(self):
        prompt = _build_prompt("unknown_module", {})
        assert isinstance(prompt, str)
