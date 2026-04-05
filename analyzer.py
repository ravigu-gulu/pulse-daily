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

GITHUB_PROMPT = """你是开源社区专家。根据以下 GitHub Trending 项目列表，输出严格的 JSON 分析报告，不要输出任何 JSON 以外的内容。

项目列表：
{data}

输出格式（严格 JSON，不加任何解释）：
{{
  "picks": [
    {{
      "name": "项目名",
      "url": "github链接",
      "description": "价值分析（50字内）",
      "use_case": "适用场景（20字内）",
      "stars_today": 0,
      "rating": 4,
      "category": "AI/ML"
    }}
  ],
  "trend_summary": "今日开源技术趋势（50字内）",
  "hot_direction": "最热技术方向（10字内）"
}}

要求：精选5个最值得关注的项目，rating为1-5星。"""


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
        "finance": FINANCE_PROMPT,
        "news":    NEWS_PROMPT,
        "ai":      AI_PROMPT,
        "github":  GITHUB_PROMPT,
    }
    tmpl = templates.get(module, "")
    data_str = json.dumps(data, ensure_ascii=False, indent=2)
    # 截断过长数据，避免超出上下文
    if len(data_str) > 8000:
        data_str = data_str[:8000] + "\n...(截断)"
    return tmpl.format(data=data_str)


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
        # codex exec 在 stdout 首行输出 JSON 响应，后续行是元信息
        # 优先取 stdout 第一行（最干净的 JSON 输出）
        first_line = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
        try:
            return json.loads(first_line)
        except json.JSONDecodeError:
            pass
        # 回退：在全部输出中搜索最后一个合法 JSON 对象
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
    """从 stdout 中提取最后一段合法 JSON 对象。"""
    if not text:
        return None
    # 找所有 {...} 块，取最后一个能解析的
    candidates = list(re.finditer(r'\{[\s\S]*\}', text))
    for match in reversed(candidates):
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            continue
    return None
