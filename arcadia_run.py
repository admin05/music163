#!/usr/bin/env python3
import logging
import os
import sys
import time
from pathlib import Path

from arcadia_notify import send_bark


PROJECT_ROOT = Path(__file__).resolve().parent
VALID_RUN_MODES = {"all", "daily", "interval"}


class ArcadiaLogCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[str] = []
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(self.format(record))
        except Exception:
            pass


def _env_summary() -> list[str]:
    return [
        f"REDIS_URL={'已配置' if os.getenv('REDIS_URL') else '未配置，使用项目默认值'}",
        f"LOGIN_METHOD={os.getenv('LOGIN_METHOD', 'playwright')}",
        f"BARK={'已配置' if os.getenv('BARK') else '未配置'}",
        f"ARC_RUN_MODE={os.getenv('ARC_RUN_MODE', 'all')}",
    ]


def _build_summary(status: str, elapsed: float, logs: list[str], error: Exception | None = None) -> str:
    important_keywords = (
        "发现 ",
        "成功",
        "失败",
        "异常",
        "跳过",
        "结果",
        "Redis",
        "登录",
        "签到",
        "分享",
        "VIP",
    )
    important = [line for line in logs if any(keyword in line for keyword in important_keywords)]
    selected = important[-18:] if important else logs[-18:]

    lines = [
        f"运行状态：{status}",
        f"耗时：{elapsed:.1f} 秒",
        *_env_summary(),
    ]
    if error:
        lines.append(f"错误信息：{error}")
    if selected:
        lines.extend(["", "关键日志：", *selected])
    else:
        lines.extend(["", "关键日志：本次没有收集到任务日志。"])
    return "\n".join(lines)


def _run_arcadia_task() -> None:
    start = time.monotonic()
    error = None
    status = "成功"
    logger = None
    collector = ArcadiaLogCollector()

    try:
        os.chdir(PROJECT_ROOT)
        run_mode = os.getenv("ARC_RUN_MODE", "all").strip().lower() or "all"
        if run_mode not in VALID_RUN_MODES:
            raise ValueError(f"ARC_RUN_MODE 只能是 all、daily 或 interval，当前值：{run_mode}")

        if "--once" not in sys.argv:
            sys.argv.append("--once")

        from core import logger as netease_logger
        from main import daily_task_runner, interval_task_runner

        logger = netease_logger
        logger.addHandler(collector)

        logger.info("Arcadia 单次任务启动")
        if run_mode in ("all", "daily"):
            daily_task_runner()
        if run_mode in ("all", "interval"):
            interval_task_runner()
        logger.info("Arcadia 单次任务结束")
    except Exception as exc:
        status = "失败"
        error = exc
        if logger:
            logger.exception("Arcadia 单次任务执行失败")
        else:
            print(f"Arcadia 单次任务启动失败：{exc}", file=sys.stderr)
        raise
    finally:
        elapsed = time.monotonic() - start
        notify_on_success = os.getenv("ARC_BARK_ON_SUCCESS", "1").strip().lower() not in ("0", "false", "no")
        title = os.getenv("ARC_BARK_TITLE", "网易音乐人任务")
        if status != "成功" or notify_on_success:
            level = "active" if status == "成功" else "timeSensitive"
            send_bark(f"{title}{status}", _build_summary(status, elapsed, collector.records, error), level=level)
        if logger:
            logger.removeHandler(collector)


def main() -> int:
    try:
        _run_arcadia_task()
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
