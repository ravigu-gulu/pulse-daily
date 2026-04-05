"""双模型分析器：Claude CLI + GPT (codex exec) 并行调用。"""
import json
import logging
import re
import subprocess
import concurrent.futures
import threading
from typing import Optional

from config import CLAUDE_MODEL, TIMEOUT_MODEL

logger = logging.getLogger(__name__)

# 限制同时运行的 Claude 进程数，避免并发过高导致空输出
_CLAUDE_SEM = threading.Semaphore(2)

# ── Prompt 模板 ───────────────────────────────────────────

FINANCE_PROMPT = """你是专业财经分析师。根据以下市场数据，输出严格的 JSON 分析报告，不要输出任何 JSON 以外的内容。

市场数据：
{data}

输出格式（严格 JSON，不加任何解释）：
{{
  "market_signals": ["最重要的市场信号1", "市场信号2", "市场信号3"],
  "gold_commodities": "黄金及大宗商品走势分析（80字内）",
  "china_market": "A股港股今日表现及分析（80字内）",
  "investment_advice": {{
    "short_term": "短期（1-4周）建议（1-2句）",
    "mid_term": "中期（1-3月）建议（1-2句）",
    "long_term": "长期（6月以上）建议（1-2句）"
  }},
  "risk_warning": "主要风险提示（50字内）",
  "watch_tomorrow": "明日关注要点（1-2条）"
}}"""

NEWS_PROMPT = """你是国际时事分析师。根据以下新闻列表，输出严格的 JSON 分析报告，不要输出任何 JSON 以外的内容。

新闻列表：
{data}

输出格式（严格 JSON，不加任何解释）：
{{
  "top_events": [
    {{
      "title": "事件标题（中文，20字内）",
      "analysis": "分析（2-3句中文，60字内）",
      "sources": ["来源1"],
      "impact_level": "高/中/低"
    }}
  ],
  "overall_summary": "整体局势综评（100字内）",
  "china_asia_impact": "对中国/亚太影响（50字内）",
  "watch_next": "明日值得关注的动态（1-2条）"
}}

要求：精选5-8条最重要事件，impact_level 为高的优先。"""

AI_PROMPT = """你是AI领域资深研究员。根据以下AI新闻和论文，输出严格的 JSON 分析报告，不要输出任何 JSON 以外的内容。

数据：
{data}

输出格式（严格 JSON，不加任何解释）：
{{
  "model_updates": [
    {{"name": "模型/产品名", "update": "更新内容（30字内）", "significance": "重要性（高/中/低）"}}
  ],
  "research_highlights": [
    {{"title": "论文/研究标题（中文）", "plain_summary": "通俗解读（60字内）", "source": "来源"}}
  ],
  "industry_moves": ["产业动态1（30字内）", "产业动态2"],
  "trend_judgment": "今日AI趋势判断（50字内）"
}}

注意：严格区分论文预印本与产业落地事实，不要将arxiv宣称写成产业结论。"""

GITHUB_PROMPT = """你是开源社区专家，同时熟悉产品经理工具和金融科技领域。根据以下三类 GitHub 项目数据，输出严格的 JSON 分析报告，不要输出任何 JSON 以外的内容。

数据：
{data}

输出格式（严格 JSON，不加任何解释）：
{{
  "trending": {{
    "picks": [
      {{
        "name": "项目名",
        "url": "github链接",
        "what": "项目是什么、核心功能（60字内）",
        "why": "核心优势与亮点，与同类项目的差异化（60字内）",
        "use_case": "具体适用场景与人群（40字内）",
        "stars_today": 0,
        "rating": 4,
        "category": "AI/ML"
      }}
    ],
    "trend_summary": "今日开源技术趋势（80字内）",
    "hot_direction": "最热技术方向（15字内）"
  }},
  "pm_tools": {{
    "picks": [
      {{
        "name": "项目名",
        "url": "github链接",
        "what": "工具是什么、解决什么问题（60字内）",
        "why": "对产品经理的核心价值与优势（60字内）",
        "use_case": "PM具体使用场景（40字内）",
        "stars": 0,
        "rating": 4
      }}
    ],
    "summary": "PM工具整体推荐语与使用建议（80字内）"
  }},
  "finance_tools": {{
    "picks": [
      {{
        "name": "项目名",
        "url": "github链接",
        "what": "项目是什么、核心功能（60字内）",
        "why": "金融行业的核心价值与优势（60字内）",
        "use_case": "适用金融业务场景（40字内）",
        "stars": 0,
        "rating": 4
      }}
    ],
    "summary": "金融开源工具整体推荐语（80字内）"
  }}
}}

要求：trending精选5个，pm_tools精选3-5个，finance_tools精选3-5个，rating为1-5星。每个字段都要有实质内容，what/why/use_case三个字段必须各自独立阐述，不能重复。"""

CLAWHUB_PROMPT = """你是AI技能生态专家，同时熟悉产品经理工具和金融科技领域。根据以下三类 ClawHub.ai 技能数据，输出严格的 JSON 分析报告，不要输出任何 JSON 以外的内容。

ClawHub.ai 是面向 AI 智能体（如 Claude Code、OpenClaw）的技能注册中心，提供向量搜索。技能（skill）是可直接加载到 AI 智能体的提示词/工具包。

数据：
{data}

输出格式（严格 JSON，不加任何解释）：
{{
  "trending": {{
    "picks": [
      {{
        "name": "技能包名",
        "displayName": "技能显示名称",
        "url": "clawhub链接",
        "what": "技能是什么、核心功能与作用（60字内）",
        "why": "核心优势与亮点，与同类技能的差异化（60字内）",
        "use_case": "具体适用场景与人群（40字内）",
        "rating": 4,
        "isOfficial": false
      }}
    ],
    "trend_summary": "今日 ClawHub 技能生态趋势（80字内）",
    "hot_direction": "最热技能方向（15字内）"
  }},
  "pm_skills": {{
    "picks": [
      {{
        "name": "技能包名",
        "displayName": "技能显示名称",
        "url": "clawhub链接",
        "what": "技能是什么、解决什么问题（60字内）",
        "why": "对产品经理的核心价值与优势（60字内）",
        "use_case": "PM具体使用场景（40字内）",
        "rating": 4,
        "isOfficial": false
      }}
    ],
    "summary": "PM技能整体推荐语与使用建议（80字内）"
  }},
  "finance_skills": {{
    "picks": [
      {{
        "name": "技能包名",
        "displayName": "技能显示名称",
        "url": "clawhub链接",
        "what": "技能是什么、核心功能（60字内）",
        "why": "金融行业的核心价值与优势（60字内）",
        "use_case": "适用金融业务场景（40字内）",
        "rating": 4,
        "isOfficial": false
      }}
    ],
    "summary": "金融技能整体推荐语（80字内）"
  }}
}}

要求：trending精选5个，pm_skills精选3-5个，finance_skills精选3-5个，rating为1-5星。每个字段都要有实质内容，what/why/use_case三个字段必须各自独立阐述，不能重复。若某类数据为空，对应picks返回空列表，summary写"暂无相关技能"。"""


# ── 双模型并行调用 ─────────────────────────────────────────

def analyze(module: str, data: dict) -> dict:
    """并行调用 Claude 和 GPT，返回 {claude: {...}, gpt: {...}}。"""
    prompt = _build_prompt(module, data)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_claude = ex.submit(_call_claude, prompt)
        f_gpt    = ex.submit(_call_gpt, prompt)

    claude_result = f_claude.result()
    gpt_result    = f_gpt.result()

    return {"claude": claude_result, "gpt": gpt_result}


def _build_prompt(module: str, data: dict) -> str:
    templates = {
        "finance":  FINANCE_PROMPT,
        "news":     NEWS_PROMPT,
        "ai":       AI_PROMPT,
        "github":   GITHUB_PROMPT,
        "clawhub":  CLAWHUB_PROMPT,
    }
    tmpl = templates.get(module, "")
    trimmed = _trim_data(module, data)
    data_str = json.dumps(trimmed, ensure_ascii=False, indent=2)
    # 保底截断，防止极端情况
    if len(data_str) > 10000:
        data_str = data_str[:10000] + "\n...(截断)"
    return tmpl.format(data=data_str)


def _trim_data(module: str, data: dict) -> dict:
    """按模块精简数据，确保 data_str 在合理大小内，避免截断破坏 JSON 结构。"""
    if module == "news":
        items = data.get("items", [])[:20]
        return {
            "items": [
                {"title": i.get("title", ""),
                 "summary": i.get("summary", "")[:150],
                 "source": i.get("source", "")}
                for i in items
            ],
            "total_raw": data.get("total_raw", 0),
        }
    if module == "ai":
        return {
            "hn": [{"title": i.get("title",""), "score": i.get("score",0)}
                   for i in data.get("hn", [])[:10]],
            "arxiv": [{"title": i.get("title",""), "summary": i.get("summary","")[:150]}
                      for i in data.get("arxiv", [])[:10]],
            "media": [{"title": i.get("title",""), "summary": i.get("summary","")[:150],
                       "source": i.get("source","")}
                      for i in data.get("media", [])[:10]],
        }
    if module == "github":
        def _slim(items, extra_keys=()):
            base = ["name", "url", "description", "language", "stars"]
            keys = list(base) + list(extra_keys)
            return [
                {k: (v[:120] if isinstance(v := i.get(k, ""), str) else v)
                 for k in keys}
                for i in items[:15]
            ]
        return {
            "trending": _slim(data.get("trending", []), ("stars_today", "category")),
            "pm":       _slim(data.get("pm", [])),
            "finance":  _slim(data.get("finance", [])),
        }
    if module == "clawhub":
        def _slim_skill(items, n=15):
            keys = ["name", "displayName", "summary", "url", "isOfficial",
                    "verificationTier", "capabilityTags"]
            return [
                {k: (v[:200] if isinstance(v := i.get(k, ""), str) else v)
                 for k in keys}
                for i in items[:n]
            ]
        return {
            "trending":       _slim_skill(data.get("trending", []), 15),
            "pm_skills":      _slim_skill(data.get("pm_skills", []), 10),
            "finance_skills": _slim_skill(data.get("finance_skills", []), 10),
        }
    # finance：数据量本身不大，直接返回
    return data


def _call_claude(prompt: str) -> dict:
    """调用 claude -p CLI（信号量限制最多 2 个并发进程）。"""
    with _CLAUDE_SEM:
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", CLAUDE_MODEL],
                capture_output=True, text=True, timeout=TIMEOUT_MODEL,
            )
            if result.returncode != 0:
                logger.warning("Claude CLI 返回非零: %s", result.stderr[:200])
            return _extract_json(result.stdout) or {"error": result.stderr[:200] or "无输出"}
        except subprocess.TimeoutExpired:
            logger.error("Claude 调用超时（%ds）", TIMEOUT_MODEL)
            return {"error": f"超时（{TIMEOUT_MODEL}s）"}
        except Exception as e:
            logger.error("Claude 调用异常: %s", e)
            return {"error": str(e)}


def _call_gpt(prompt: str) -> dict:
    """调用 codex exec CLI（默认 gpt-5.4），提取最后一段合法 JSON。"""
    try:
        result = subprocess.run(
            ["codex", "exec", prompt,
             "-c", "sandbox_permissions=[\"disk-full-read-access\"]"],
            capture_output=True, text=True, timeout=TIMEOUT_MODEL,
        )
        if result.returncode != 0:
            logger.warning("GPT CLI 返回非零: %s", result.stderr[:200])
            return {"error": result.stderr[:200] or "GPT CLI 非零退出"}
        # codex exec 在 stdout 首行输出 JSON 响应，后续行是元信息
        # 优先取 stdout 第一行（最干净的 JSON 输出）
        first_line = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
        try:
            return json.loads(first_line)
        except json.JSONDecodeError:
            pass
        # 回退：括号平衡扫描提取最后一个完整 JSON 对象
        parsed = _extract_json(result.stdout)
        if parsed:
            return parsed
        logger.warning("GPT 输出无法解析 JSON，返回原始文本摘要")
        return {"error": "输出格式异常", "raw": result.stdout[-500:]}
    except subprocess.TimeoutExpired:
        logger.error("GPT 调用超时（%ds）", TIMEOUT_MODEL)
        return {"error": f"超时（{TIMEOUT_MODEL}s）"}
    except Exception as e:
        logger.error("GPT 调用异常: %s", e)
        return {"error": str(e)}


def _extract_json(text: str) -> Optional[dict]:
    """括号平衡扫描，返回文本中最大的合法 JSON 对象（外层 wrapper 总比子对象大）。"""
    if not text:
        return None
    best: Optional[dict] = None
    best_len = 0
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        depth, in_str, escape = 0, False, False
        j = i
        while j < len(text):
            ch = text[j]
            if escape:
                escape = False
            elif ch == "\\" and in_str:
                escape = True
            elif ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        span = j - i + 1
                        if span > best_len:
                            candidate = text[i:j + 1]
                            try:
                                best = json.loads(candidate)
                                best_len = span
                            except json.JSONDecodeError:
                                pass
                        break
            j += 1
        i += 1
    return best
