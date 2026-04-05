"""HTML 日报生成器：只吃 JSON，模板渲染。"""
import html
from datetime import date, datetime
from typing import Optional

from config import TZ_CST


def build_report(results: dict, report_date: date) -> str:
    now_str = datetime.now(TZ_CST).strftime("%Y-%m-%d %H:%M CST")
    sections = ""

    if "finance" in results:
        sections += _render_finance(results["finance"])
    if "news" in results:
        sections += _render_news(results["news"])
    if "ai" in results:
        sections += _render_ai(results["ai"])
    if "github" in results:
        sections += _render_github(results["github"])

    return HTML_TMPL.format(
        report_date=report_date.strftime("%Y年%m月%d日"),
        weekday=["周一","周二","周三","周四","周五","周六","周日"][report_date.weekday()],
        generated=now_str,
        sections=sections,
    )


# ── 财经模块 ──────────────────────────────────────────────

def _render_finance(data: dict) -> str:
    raw     = data.get("raw", {})
    tickers = raw.get("tickers", {})
    groups  = raw.get("groups", {})
    claude  = data.get("claude", {})
    gpt     = data.get("gpt", {})

    panel = _finance_panel(tickers, groups)
    claude_html = _finance_analysis(claude, "claude")
    gpt_html    = _finance_analysis(gpt, "gpt")

    return _section("📈 每日财经分析", panel + _dual_tab(claude_html, gpt_html, "finance"))


def _finance_panel(tickers: dict, groups: dict) -> str:
    group_labels = {
        "us": "🇺🇸 美股", "china": "🇨🇳 A股",
        "hk": "🇭🇰 港股", "metals": "🏅 黄金/大宗",
        "fx": "💱 汇率", "crypto": "₿ 加密货币",
    }
    rows = ""
    for gkey, label in group_labels.items():
        syms = groups.get(gkey, [])
        if not syms:
            continue
        rows += f'<tr class="group-header"><td colspan="4">{label}</td></tr>'
        for sym in syms:
            t = tickers.get(sym, {})
            name      = t.get("name", sym)
            price     = t.get("price")
            chg       = t.get("change")
            chg_pct   = t.get("change_pct")
            status    = t.get("market_status", "")
            currency  = t.get("currency", "")

            if price is None:
                rows += f'<tr><td>{_e(name)}</td><td colspan="3" class="na">数据获取失败</td></tr>'
                continue

            cls = "up" if (chg or 0) >= 0 else "dn"
            sign = "+" if (chg or 0) >= 0 else ""
            status_badge = '<span class="closed-badge">休市</span>' if status == "closed" else ""
            rows += (
                f'<tr><td class="ticker-name">{_e(name)} {status_badge}</td>'
                f'<td class="price">{_fmt_price(price, currency)}</td>'
                f'<td class="{cls}">{sign}{chg:.2f}</td>'
                f'<td class="{cls}">{sign}{chg_pct:.2f}%</td></tr>'
            )
    return f'<table class="market-table"><thead><tr><th>市场</th><th>最新价</th><th>涨跌</th><th>涨跌幅</th></tr></thead><tbody>{rows}</tbody></table>'


def _finance_analysis(data: dict, side: str) -> str:
    if "error" in data:
        return f'<p class="err-msg">分析失败：{_e(str(data["error"]))}</p>'
    signals = data.get("market_signals", [])
    gold    = data.get("gold_commodities", "")
    china   = data.get("china_market", "")
    advice  = data.get("investment_advice", {})
    risk    = data.get("risk_warning", "")
    watch   = data.get("watch_tomorrow", "")

    signals_html = "".join(f'<li>{_e(s)}</li>' for s in signals)
    advice_html  = ""
    for k, label in [("short_term","短期"),("mid_term","中期"),("long_term","长期")]:
        v = advice.get(k, "")
        if v:
            advice_html += f'<div class="advice-item"><span class="advice-label">{label}</span>{_e(v)}</div>'

    return f"""
<div class="analysis-block">
  <h4>核心市场信号</h4><ul class="signal-list">{signals_html}</ul>
  <h4>黄金 / 大宗商品</h4><p>{_e(gold)}</p>
  <h4>A股 / 港股</h4><p>{_e(china)}</p>
  <h4>投资建议</h4>{advice_html}
  <div class="risk-box">⚠️ 风险提示：{_e(risk)}</div>
  <div class="watch-box">👀 明日关注：{_e(str(watch))}</div>
</div>"""


# ── 国际局势模块 ──────────────────────────────────────────

def _render_news(data: dict) -> str:
    raw    = data.get("raw", {})
    claude = data.get("claude", {})
    gpt    = data.get("gpt", {})

    total = raw.get("total_raw", 0)
    meta  = f'<p class="meta-info">共抓取 {total} 条新闻，去重过滤后分析</p>'
    claude_html = _news_analysis(claude)
    gpt_html    = _news_analysis(gpt)

    return _section("🌍 国际重要局势", meta + _dual_tab(claude_html, gpt_html, "news"))


def _news_analysis(data: dict) -> str:
    if "error" in data:
        return f'<p class="err-msg">分析失败：{_e(str(data["error"]))}</p>'
    events  = data.get("top_events", [])
    summary = data.get("overall_summary", "")
    impact  = data.get("china_asia_impact", "")
    watch   = data.get("watch_next", "")

    events_html = ""
    for ev in events:
        lvl = ev.get("impact_level", "中")
        cls = {"高": "impact-high", "中": "impact-mid", "低": "impact-low"}.get(lvl, "impact-mid")
        srcs = "、".join(ev.get("sources", []))
        events_html += f"""
<div class="event-card {cls}">
  <div class="event-title">{_e(ev.get('title',''))}</div>
  <div class="event-analysis">{_e(ev.get('analysis',''))}</div>
  <div class="event-meta">来源：{_e(srcs)} · 重要性：{lvl}</div>
</div>"""

    return f"""
<div class="analysis-block">
  {events_html}
  <div class="summary-box"><strong>综评：</strong>{_e(summary)}</div>
  <div class="impact-box"><strong>中国/亚太影响：</strong>{_e(impact)}</div>
  <div class="watch-box">👀 明日关注：{_e(str(watch))}</div>
</div>"""


# ── AI 进展模块 ───────────────────────────────────────────

def _render_ai(data: dict) -> str:
    raw    = data.get("raw", {})
    claude = data.get("claude", {})
    gpt    = data.get("gpt", {})

    hn_cnt = len(raw.get("hn", []))
    ax_cnt = len(raw.get("arxiv", []))
    md_cnt = len(raw.get("media", []))
    meta   = f'<p class="meta-info">HN热帖 {hn_cnt} 条 · arxiv论文 {ax_cnt} 篇 · 科技媒体 {md_cnt} 条</p>'

    claude_html = _ai_analysis(claude)
    gpt_html    = _ai_analysis(gpt)
    return _section("🤖 每日 AI 进展", meta + _dual_tab(claude_html, gpt_html, "ai"))


def _ai_analysis(data: dict) -> str:
    if "error" in data:
        return f'<p class="err-msg">分析失败：{_e(str(data["error"]))}</p>'

    model_updates = data.get("model_updates", [])
    research      = data.get("research_highlights", [])
    industry      = data.get("industry_moves", [])
    trend         = data.get("trend_judgment", "")

    mu_html = ""
    for m in model_updates:
        sig = m.get("significance", "中")
        cls = "sig-high" if sig == "高" else ("sig-low" if sig == "低" else "")
        mu_html += f'<div class="model-update {cls}"><span class="model-name">{_e(m.get("name",""))}</span>{_e(m.get("update",""))}</div>'

    rh_html = ""
    for r in research:
        rh_html += f'<div class="research-item"><div class="research-title">{_e(r.get("title",""))}</div><div class="research-summary">{_e(r.get("plain_summary",""))}</div><span class="research-source">{_e(r.get("source",""))}</span></div>'

    ind_html = "".join(f'<li>{_e(i)}</li>' for i in industry)

    return f"""
<div class="analysis-block">
  <h4>大模型动态</h4>{mu_html if mu_html else '<p class="na">暂无</p>'}
  <h4>研究进展</h4>{rh_html if rh_html else '<p class="na">暂无</p>'}
  <h4>行业应用动态</h4><ul class="signal-list">{ind_html}</ul>
  <div class="watch-box">📊 趋势判断：{_e(trend)}</div>
</div>"""


# ── GitHub 开源精选（三章节） ─────────────────────────────

def _render_github(data: dict) -> str:
    raw    = data.get("raw", {})
    claude = data.get("claude", {})
    gpt    = data.get("gpt", {})

    total_trending = len(raw.get("trending", raw.get("items", [])))
    total_pm       = len(raw.get("pm", []))
    total_finance  = len(raw.get("finance", []))
    meta = (f'<p class="meta-info">Trending {total_trending} 个 · '
            f'PM工具 {total_pm} 个 · 金融项目 {total_finance} 个</p>')

    # 子章节 1：Trending
    trending_html = _subsection(
        "🔥 GitHub Trending",
        _dual_tab(
            _github_trending(claude.get("trending", claude) if "trending" in claude else claude),
            _github_trending(gpt.get("trending", gpt) if "trending" in gpt else gpt),
            "github_trending"
        )
    )

    # 子章节 2：PM 专项
    pm_html = _subsection(
        "🧩 产品经理专项推荐",
        _dual_tab(
            _github_picks(claude.get("pm_tools", {}), stars_key="stars"),
            _github_picks(gpt.get("pm_tools", {}), stars_key="stars"),
            "github_pm"
        )
    )

    # 子章节 3：金融行业
    finance_html = _subsection(
        "🏦 金融/银行业项目推荐",
        _dual_tab(
            _github_picks(claude.get("finance_tools", {}), stars_key="stars"),
            _github_picks(gpt.get("finance_tools", {}), stars_key="stars"),
            "github_finance"
        )
    )

    return _section("⭐ GitHub 开源精选", meta + trending_html + pm_html + finance_html)


def _github_trending(data: dict) -> str:
    if "error" in data:
        return f'<p class="err-msg">分析失败：{_e(str(data["error"]))}</p>'
    picks  = data.get("picks", [])
    trend  = data.get("trend_summary", "")
    hotdir = data.get("hot_direction", "")
    picks_html = _repo_cards(picks, stars_key="stars_today", show_cat=True)
    return f"""
<div class="analysis-block">
  {picks_html}
  <div class="summary-box"><strong>趋势：</strong>{_e(trend)}</div>
  <div class="watch-box">🔥 最热方向：{_e(hotdir)}</div>
</div>"""


def _github_picks(data: dict, stars_key: str = "stars") -> str:
    if not data or "error" in data:
        err = data.get("error", "") if data else ""
        return f'<p class="err-msg">分析失败：{_e(str(err))}</p>' if err else '<p class="na">暂无数据</p>'
    picks   = data.get("picks", [])
    summary = data.get("summary", "")
    picks_html = _repo_cards(picks, stars_key=stars_key, show_cat=False)
    return f"""
<div class="analysis-block">
  {picks_html}
  <div class="summary-box"><strong>推荐语：</strong>{_e(summary)}</div>
</div>"""


def _repo_cards(picks: list, stars_key: str = "stars_today", show_cat: bool = True) -> str:
    html = ""
    for p in picks:
        stars  = p.get(stars_key, p.get("stars", 0))
        rating = "⭐" * max(1, min(_safe_int(p.get("rating"), 3), 5))
        cat    = f'<span class="repo-cat">{_e(p.get("category",""))}</span>' if show_cat else ""
        stars_label = f"+{stars}⭐" if stars_key == "stars_today" else f"★{stars:,}"

        # 兼容旧 description 字段和新 what/why/use_case 三字段
        what     = _e(p.get("what", p.get("description", "")))
        why      = _e(p.get("why", ""))
        use_case = _e(p.get("use_case", ""))

        detail = ""
        if what:
            detail += f'<div class="repo-what"><span class="repo-field-label">📌 项目内容：</span>{what}</div>'
        if why:
            detail += f'<div class="repo-why"><span class="repo-field-label">✨ 核心优势：</span>{why}</div>'
        if use_case:
            detail += f'<div class="repo-usecase"><span class="repo-field-label">🎯 适用场景：</span>{use_case}</div>'

        html += f"""
<div class="repo-card">
  <div class="repo-header">
    <a href="{_e(p.get('url',''))}" target="_blank" class="repo-name">{_e(p.get('name',''))}</a>
    {cat}
    <span class="repo-stars">{stars_label}</span>
  </div>
  <div class="repo-detail">{detail}</div>
  <div class="repo-meta">{rating}</div>
</div>"""
    return html


def _subsection(title: str, content: str) -> str:
    return f'<div class="subsection"><h3>{title}</h3>{content}</div>'


# ── 通用辅助 ──────────────────────────────────────────────

def _e(s: str) -> str:
    return html.escape(str(s))


def _safe_int(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _fmt_price(price: float, currency: str) -> str:
    if currency in ("CNY", "CNY/USD"):
        return f"{price:,.2f}"
    if currency == "USD":
        return f"${price:,.2f}"
    if currency == "HKD":
        return f"HK${price:,.2f}"
    return f"{price:,.4f}"


def _section(title: str, content: str) -> str:
    return f"""
<section>
  <h2>{title}</h2>
  {content}
</section>"""


def _dual_tab(claude_html: str, gpt_html: str, uid: str) -> str:
    return f"""
<div class="dual-tab">
  <div class="tab-btns">
    <button class="tab-btn active" onclick="switchTab('{uid}','claude',this)">🔵 Claude Opus 4.6</button>
    <button class="tab-btn" onclick="switchTab('{uid}','gpt',this)">🟢 GPT 分析</button>
  </div>
  <div id="{uid}-claude" class="tab-panel claude-panel">{claude_html}</div>
  <div id="{uid}-gpt"    class="tab-panel gpt-panel" style="display:none">{gpt_html}</div>
</div>"""


# ── HTML 模板 ─────────────────────────────────────────────

HTML_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PulseDaily · {report_date}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;color:#1a1a2e;padding:16px;max-width:900px;margin:0 auto}}

/* 头部 */
.hdr{{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);color:#fff;padding:24px 28px;border-radius:14px;margin-bottom:18px}}
.hdr h1{{font-size:22px;font-weight:700;letter-spacing:1px}}
.hdr .sub{{font-size:13px;opacity:.7;margin-top:6px}}
.hdr .meta{{font-size:11px;opacity:.5;margin-top:4px}}

/* 模块卡片 */
section{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:16px;box-shadow:0 2px 10px rgba(0,0,0,.07)}}
h2{{font-size:16px;font-weight:700;color:#0f3460;margin-bottom:14px;padding-bottom:10px;border-bottom:2px solid #e8f4ff}}
h4{{font-size:13px;font-weight:600;color:#444;margin:14px 0 6px}}

/* 双模型 Tab */
.dual-tab{{margin-top:12px}}
.tab-btns{{display:flex;gap:8px;margin-bottom:12px}}
.tab-btn{{padding:6px 16px;border:1.5px solid #ddd;border-radius:20px;background:#f9f9f9;cursor:pointer;font-size:12px;font-weight:500;transition:all .2s}}
.tab-btn.active{{background:#1677ff;color:#fff;border-color:#1677ff}}
.tab-panel{{animation:fadeIn .2s}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}
.claude-panel{{border-left:3px solid #1677ff;padding-left:12px}}
.gpt-panel{{border-left:3px solid #52c41a;padding-left:12px}}

/* 财经面板 */
.market-table{{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:14px}}
.market-table th{{background:#fafafa;color:#888;font-weight:500;text-align:left;padding:8px 10px;border-bottom:1px solid #f0f0f0}}
.market-table td{{padding:7px 10px;border-bottom:1px solid #f5f5f5}}
.group-header td{{background:#f0f7ff;font-weight:600;color:#0f3460;font-size:12px;padding:5px 10px}}
.ticker-name{{font-weight:500;color:#333}}
.price{{font-weight:700;font-family:monospace}}
.up{{color:#cf1322;font-weight:600}}
.dn{{color:#389e0d;font-weight:600}}
.closed-badge{{font-size:10px;background:#f5f5f5;color:#999;padding:1px 6px;border-radius:8px;margin-left:4px}}

/* 分析块 */
.analysis-block{{font-size:13px;line-height:1.7}}
.signal-list{{padding-left:18px;margin:6px 0}}
.signal-list li{{margin-bottom:4px}}
.advice-item{{margin:6px 0;padding:8px 12px;background:#f8faff;border-radius:6px}}
.advice-label{{display:inline-block;background:#e6f4ff;color:#1677ff;font-size:11px;padding:1px 8px;border-radius:10px;margin-right:8px;font-weight:600}}
.risk-box{{margin-top:10px;padding:8px 12px;background:#fff7e6;border-left:3px solid #fa8c16;font-size:12px;color:#873800;border-radius:4px}}
.watch-box{{margin-top:8px;padding:8px 12px;background:#f6ffed;border-left:3px solid #52c41a;font-size:12px;color:#135200;border-radius:4px}}
.summary-box{{margin-top:10px;padding:8px 12px;background:#f9f0ff;border-left:3px solid #722ed1;font-size:12px;border-radius:4px}}
.impact-box{{margin-top:8px;padding:8px 12px;background:#e6f7ff;border-left:3px solid #1677ff;font-size:12px;border-radius:4px}}

/* 新闻事件卡片 */
.event-card{{margin-bottom:10px;padding:10px 14px;border-radius:8px;border-left:4px solid #ddd}}
.impact-high{{border-left-color:#cf1322;background:#fff1f0}}
.impact-mid{{border-left-color:#fa8c16;background:#fffbe6}}
.impact-low{{border-left-color:#52c41a;background:#f6ffed}}
.event-title{{font-weight:600;font-size:13px;margin-bottom:4px}}
.event-analysis{{font-size:12px;color:#444;line-height:1.6}}
.event-meta{{font-size:11px;color:#999;margin-top:4px}}

/* 模型动态 */
.model-update{{padding:6px 12px;margin-bottom:6px;background:#f8faff;border-radius:6px;font-size:12px}}
.model-name{{font-weight:600;color:#0f3460;margin-right:8px}}
.sig-high{{border-left:3px solid #cf1322}}
.sig-low{{border-left:3px solid #999}}

/* 研究论文 */
.research-item{{padding:8px 12px;margin-bottom:8px;background:#fafafa;border-radius:6px}}
.research-title{{font-weight:600;font-size:12px;color:#333;margin-bottom:3px}}
.research-summary{{font-size:12px;color:#555;line-height:1.5}}
.research-source{{font-size:11px;color:#999;margin-top:3px;display:inline-block}}

/* GitHub 子章节 */
.subsection{{margin-bottom:24px}}
.subsection h3{{font-size:15px;font-weight:700;color:#333;margin:0 0 10px;padding-bottom:6px;border-bottom:2px solid #f0f0f0}}
/* GitHub 项目卡片 */
.repo-card{{padding:12px 16px;margin-bottom:10px;border:1px solid #f0f0f0;border-radius:8px;background:#fafafa}}
.repo-header{{display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap}}
.repo-name{{font-weight:700;font-size:13px;color:#1677ff;text-decoration:none}}
.repo-name:hover{{text-decoration:underline}}
.repo-cat{{font-size:11px;background:#e6f4ff;color:#0958d9;padding:1px 8px;border-radius:10px}}
.repo-stars{{font-size:11px;color:#fa8c16;font-weight:600;margin-left:auto}}
.repo-detail{{margin-bottom:6px}}
.repo-what,.repo-why,.repo-usecase{{font-size:12px;color:#444;line-height:1.6;margin-bottom:3px}}
.repo-field-label{{font-weight:600;color:#555;margin-right:4px}}
.repo-meta{{font-size:11px;color:#888}}

/* 通用 */
.meta-info{{font-size:11px;color:#aaa;margin-bottom:10px}}
.na{{color:#bbb;font-style:italic}}
.err-msg{{color:#cf1322;font-size:12px;padding:8px;background:#fff1f0;border-radius:4px}}
footer{{text-align:center;color:#bbb;font-size:11px;margin-top:16px;line-height:2}}
</style>
</head>
<body>

<div class="hdr">
  <h1>⚡ PulseDaily · 全球脉搏日报</h1>
  <div class="sub">{report_date} {weekday}</div>
  <div class="meta">生成时间：{generated} · 数据来源：BBC/Reuters/yfinance/HN/arxiv/GitHub</div>
</div>

{sections}

<footer>
  PulseDaily · 数据仅供参考，不构成投资建议<br>
  投资有风险，决策需谨慎 · 生成时间：{generated}
</footer>

<script>
function switchTab(uid, side, btn) {{
  document.getElementById(uid+'-claude').style.display = 'none';
  document.getElementById(uid+'-gpt').style.display = 'none';
  document.getElementById(uid+'-'+side).style.display = 'block';
  btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}}
</script>
</body>
</html>"""
