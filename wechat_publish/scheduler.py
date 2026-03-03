import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from .service import run_wechat_publish_pipeline


LOGGER = logging.getLogger("wechat_publish.scheduler")


@dataclass
class SchedulerConfig:
    cron_expr: str
    timezone_name: str
    runs_dir: Path
    run_arxiv_module: bool
    run_journal_module: bool
    poll_seconds: int
    target_date_mode: str


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_cron_hour_minute(cron_expr: str) -> tuple[int, int]:
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"WECHAT_SCHEDULE_CRON 格式错误: {cron_expr}")
    minute_raw, hour_raw = parts[0], parts[1]
    if not minute_raw.isdigit() or not hour_raw.isdigit():
        raise ValueError(f"WECHAT_SCHEDULE_CRON 仅支持固定时分: {cron_expr}")

    minute = int(minute_raw)
    hour = int(hour_raw)
    if minute < 0 or minute > 59 or hour < 0 or hour > 23:
        raise ValueError(f"WECHAT_SCHEDULE_CRON 超出范围: {cron_expr}")
    return hour, minute


def load_scheduler_config() -> SchedulerConfig:
    return SchedulerConfig(
        cron_expr=os.environ.get("WECHAT_SCHEDULE_CRON", "0 8 * * *"),
        timezone_name=os.environ.get("WECHAT_SCHEDULE_TZ", "Asia/Shanghai"),
        runs_dir=Path(os.environ.get("WECHAT_RUNS_DIR", "./data/wechat_publish_runs")),
        run_arxiv_module=_as_bool(os.environ.get("WECHAT_RUN_ARXIV_MODULE"), True),
        run_journal_module=_as_bool(os.environ.get("WECHAT_RUN_JOURNAL_MODULE"), True),
        poll_seconds=max(5, int(os.environ.get("WECHAT_SCHEDULER_POLL_SECONDS", "20"))),
        target_date_mode=os.environ.get("WECHAT_SCHEDULE_TARGET_DATE", "today").strip().lower(),
    )


def _setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _now(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def _next_daily_run(now: datetime, hour: int, minute: int) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _target_date_str(now: datetime, mode: str) -> str:
    if mode == "today":
        return now.date().strftime("%Y-%m-%d")
    if mode == "yesterday":
        return (now.date() - timedelta(days=1)).strftime("%Y-%m-%d")
    raise ValueError("WECHAT_SCHEDULE_TARGET_DATE 只能是 today 或 yesterday")


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _record_run(
    cfg: SchedulerConfig,
    started_at: datetime,
    request_payload: dict[str, Any],
    result_payload: dict[str, Any] | None,
    error_text: str | None,
) -> None:
    date_dir = cfg.runs_dir / started_at.strftime("%Y-%m-%d")
    run_id = started_at.strftime("%Y%m%d-%H%M%S")
    run_dir = date_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_json(run_dir / "request.json", request_payload)

    record: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "request": request_payload,
        "status": "failed" if error_text else "success",
    }
    if result_payload is not None:
        _write_json(run_dir / "result.json", result_payload)
        record["result"] = result_payload
    if error_text:
        (run_dir / "error.txt").write_text(error_text, encoding="utf-8")
        record["error"] = error_text

    _append_jsonl(cfg.runs_dir / "runs.jsonl", record)


def execute_once(cfg: SchedulerConfig, date_set: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    now = _now(cfg.timezone_name)
    target_date = date_set or _target_date_str(now, cfg.target_date_mode)

    request_payload = {
        "date_set": target_date,
        "dry_run": dry_run,
        "run_arxiv_module": cfg.run_arxiv_module,
        "run_journal_module": cfg.run_journal_module,
    }
    LOGGER.info(
        "开始执行发布任务 date=%s dry_run=%s arxiv=%s journal=%s",
        target_date,
        dry_run,
        cfg.run_arxiv_module,
        cfg.run_journal_module,
    )

    started_at = _now(cfg.timezone_name)
    try:
        result = run_wechat_publish_pipeline(
            date_set=target_date,
            dry_run=dry_run,
            run_arxiv_module=cfg.run_arxiv_module,
            run_journal_module=cfg.run_journal_module,
        )
        _record_run(cfg, started_at, request_payload, result, None)
        LOGGER.info("发布任务成功 articles=%s draft_media_id=%s", result.get("articles_count"), result.get("draft_media_id"))
        return result
    except Exception as exc:
        _record_run(cfg, started_at, request_payload, None, str(exc))
        LOGGER.exception("发布任务失败")
        raise


def run_daemon(cfg: SchedulerConfig, dry_run: bool = False) -> None:
    hour, minute = _parse_cron_hour_minute(cfg.cron_expr)

    lock_path = cfg.runs_dir / "scheduler.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
    except FileExistsError:
        raise RuntimeError(f"scheduler 已在运行: {lock_path}")

    os.write(fd, str(os.getpid()).encode("utf-8"))

    def _cleanup_and_exit(signum: int, _frame: Any) -> None:
        LOGGER.info("收到信号 %s，准备退出", signum)
        try:
            os.close(fd)
        finally:
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _cleanup_and_exit)
    signal.signal(signal.SIGTERM, _cleanup_and_exit)

    state_path = cfg.runs_dir / "scheduler_state.json"
    state = _read_json(state_path, {"last_scheduled_for": ""})

    now = _now(cfg.timezone_name)
    next_run = _next_daily_run(now, hour, minute)

    LOGGER.info(
        "调度器启动 cron='%s' tz=%s next_run=%s runs_dir=%s",
        cfg.cron_expr,
        cfg.timezone_name,
        next_run.isoformat(),
        cfg.runs_dir,
    )

    try:
        while True:
            now = _now(cfg.timezone_name)
            if now >= next_run:
                schedule_day = next_run.strftime("%Y-%m-%d")
                if state.get("last_scheduled_for") == schedule_day:
                    LOGGER.warning("检测到当天任务已执行，跳过 schedule_day=%s", schedule_day)
                else:
                    try:
                        execute_once(cfg, dry_run=dry_run)
                    finally:
                        state["last_scheduled_for"] = schedule_day
                        _write_json(state_path, state)

                next_run = _next_daily_run(now + timedelta(seconds=1), hour, minute)
                LOGGER.info("下次执行时间: %s", next_run.isoformat())

            sleep_seconds = min(cfg.poll_seconds, max(1, int((next_run - now).total_seconds())))
            time.sleep(sleep_seconds)
    finally:
        try:
            os.close(fd)
        finally:
            lock_path.unlink(missing_ok=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WeChat publish 定时服务")
    parser.add_argument("--once", action="store_true", help="仅执行一次后退出")
    parser.add_argument("--date", dest="date_set", default=None, help="仅一次执行时使用，格式 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="只生成不提交微信")
    parser.add_argument("--log-level", default="INFO", help="日志级别，默认 INFO")
    return parser


def main() -> int:
    load_dotenv(override=False)
    parser = build_arg_parser()
    args = parser.parse_args()

    _setup_logging(args.log_level)

    cfg = load_scheduler_config()

    if args.once:
        execute_once(cfg, date_set=args.date_set, dry_run=args.dry_run)
        return 0

    run_daemon(cfg, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
