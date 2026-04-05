#!/usr/bin/env python3
"""
PulseDaily 主程序。
用法：
    python main.py              # 完整运行（抓取 + 分析 + 生成报告）
    python main.py --report     # 仅用已有快照重新生成报告
"""
import argparse
import concurrent.futures
import json
import logging
import signal
import sys
from datetime import date, datetime
from pathlib import Path

from config import (REPORTS_DIR, SNAPSHOTS_DIR, TZ_CST, TIMEOUT_GLOBAL)
from analyzer import analyze
from reporter import build_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_module(name: str, fetch_fn, today_snap: Path) -> dict:
    """运行单个模块：抓取 → 分析 → 返回结果。捕获所有异常。"""
    logger.info("[%s] 开始抓取...", name)
    try:
        raw = fetch_fn()
        # 保存原始数据快照
        snap_file = today_snap / f"{name}_raw.json"
        snap_file.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[%s] 抓取完成，开始双模型分析...", name)
    except Exception:
        logger.exception("[%s] 抓取失败", name)
        return {"raw": {}, "claude": {"error": "数据抓取失败"}, "gpt": {"error": "数据抓取失败"}}

    try:
        result = analyze(name, raw)
        # 保存分析结果快照
        for side in ("claude", "gpt"):
            snap_file = today_snap / f"{name}_{side}.json"
            snap_file.write_text(
                json.dumps(result.get(side, {}), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        logger.info("[%s] 分析完成", name)
        return {"raw": raw, **result}
    except Exception:
        logger.exception("[%s] 分析失败", name)
        return {"raw": raw, "claude": {"error": "模型分析失败"}, "gpt": {"error": "模型分析失败"}}


def do_run(today: date) -> dict:
    """并行运行所有模块，返回 results 字典。"""
    from fetchers.finance  import fetch_finance
    from fetchers.news     import fetch_news
    from fetchers.ai_news  import fetch_ai_news
    from fetchers.github   import fetch_github
    from fetchers.clawhub  import fetch_clawhub

    today_snap = SNAPSHOTS_DIR / today.strftime("%Y-%m-%d")
    today_snap.mkdir(parents=True, exist_ok=True)

    modules = {
        "finance": fetch_finance,
        "news":    fetch_news,
        "ai":      fetch_ai_news,
        "github":  fetch_github,
        "clawhub": fetch_clawhub,
    }

    _ERR = lambda msg: {"raw": {}, "claude": {"error": msg}, "gpt": {"error": msg}}

    results = {}
    # 4 个模块并行
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {
            ex.submit(run_module, name, fn, today_snap): name
            for name, fn in modules.items()
        }
        try:
            completed = concurrent.futures.as_completed(futures, timeout=TIMEOUT_GLOBAL)
            for future in completed:
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception:
                    logger.exception("[%s] 模块异常", name)
                    results[name] = _ERR("模块异常")
        except concurrent.futures.TimeoutError:
            logger.error("全局超时（%ds），已完成 %d/%d 个模块",
                         TIMEOUT_GLOBAL, len(results), len(modules))
            for name in modules:
                if name not in results:
                    results[name] = _ERR("全局超时")

    return results


def do_report_only(today: date) -> dict:
    """从快照加载已有数据重新生成报告。"""
    snap_dir = SNAPSHOTS_DIR / today.strftime("%Y-%m-%d")
    if not snap_dir.exists():
        logger.error("找不到 %s 的快照，请先运行完整抓取", today)
        sys.exit(1)

    def _load(path: Path, fallback: dict) -> dict:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("快照读取失败 %s: %s", path.name, exc)
            return {"error": "快照损坏"}

    results = {}
    for name in ("finance", "news", "ai", "github", "clawhub"):
        results[name] = {
            "raw":    _load(snap_dir / f"{name}_raw.json",    {}),
            "claude": _load(snap_dir / f"{name}_claude.json", {"error": "无快照"}),
            "gpt":    _load(snap_dir / f"{name}_gpt.json",    {"error": "无快照"}),
        }
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", action="store_true", help="仅用快照重新生成报告")
    args = p.parse_args()

    today = datetime.now(TZ_CST).date()
    REPORTS_DIR.mkdir(exist_ok=True)
    SNAPSHOTS_DIR.mkdir(exist_ok=True)

    logger.info("PulseDaily 开始运行 %s", today)

    if args.report:
        results = do_report_only(today)
    else:
        results = do_run(today)

    html = build_report(results, today)
    out  = REPORTS_DIR / f"pulse_{today.strftime('%Y%m%d')}.html"
    out.write_text(html, encoding="utf-8")
    logger.info("日报已生成：%s", out)
    print(f"\n报告路径: {out}")


if __name__ == "__main__":
    main()
