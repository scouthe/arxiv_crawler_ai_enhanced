import argparse
import json
import logging
import os
import signal
import socket
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TextIO
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from .email_alert import (
    EmailAlertConfig,
    load_email_alert_config_from_env,
    send_email,
)
from .models import WechatConnectivityPrecheckError
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
    email_alert_config: EmailAlertConfig


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
        email_alert_config=load_email_alert_config_from_env(),
    )


def _setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def _now(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


class _TeeStream:
    """同时写入终端和日志文件。"""

    def __init__(self, primary: TextIO, mirror: TextIO):
        self.primary = primary
        self.mirror = mirror

    def write(self, data: str) -> int:
        self.primary.write(data)
        self.mirror.write(data)
        return len(data)

    def flush(self) -> None:
        self.primary.flush()
        self.mirror.flush()

    def isatty(self) -> bool:
        return self.primary.isatty()

    def fileno(self) -> int:
        return self.primary.fileno()


def _open_run_log_file(args: argparse.Namespace) -> tuple[Path, TextIO]:
    logs_dir_raw = (
        os.environ.get("MIDPLATFORM_TASK_LOG_DIR")
        or os.environ.get("WECHAT_LOG_DIR")
        or "./logs"
    )
    logs_dir = Path(logs_dir_raw).expanduser().resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = "once" if args.once else "daemon"
    date_tag = args.date_set if args.date_set else "auto"
    dry_tag = "_dryrun" if args.dry_run else ""
    file_path = (logs_dir / f"wechat_scheduler_{ts}_{mode}_{date_tag}{dry_tag}.log").resolve()
    return file_path, file_path.open("a", encoding="utf-8")


def _report_external_log_path(log_path: Path) -> None:
    """
    中台任务模式日志上报协议：
    输出一行 JSON 到 stdout，包含 external_log_path。
    """
    task_log_dir_raw = os.environ.get("MIDPLATFORM_TASK_LOG_DIR")
    if not task_log_dir_raw:
        return

    try:
        task_log_dir = Path(task_log_dir_raw).expanduser().resolve()
        resolved_log = log_path.expanduser().resolve()
        try:
            resolved_log.relative_to(task_log_dir)
        except ValueError:
            print(
                f"[WARN] log path {resolved_log} is not inside MIDPLATFORM_TASK_LOG_DIR={task_log_dir}",
                file=sys.stderr,
            )
            return

        # 这行会被中台解析并记录到 run.external_log_path
        print(json.dumps({"external_log_path": str(resolved_log)}, ensure_ascii=False), flush=True)
    except Exception as exc:
        print(f"[WARN] failed to report external_log_path: {exc}", file=sys.stderr)


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
) -> Path:
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
        payload_status = result_payload.get("status")
        if isinstance(payload_status, str) and payload_status.strip():
            record["status"] = payload_status

    if result_payload is not None:
        _write_json(run_dir / "result.json", result_payload)
        record["result"] = result_payload
    if error_text:
        (run_dir / "error.txt").write_text(error_text, encoding="utf-8")
        record["error"] = error_text

    _append_jsonl(cfg.runs_dir / "runs.jsonl", record)
    return run_dir


def _failed_result_payload(
    *,
    target_date: str,
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "date": target_date,
        "articles_count": 0,
        "draft_media_id": None,
        "article_titles": [],
        "diagnostics": diagnostics or {},
    }


def _label_from_result(
    result_payload: dict[str, Any],
    precheck_error: WechatConnectivityPrecheckError | None,
) -> str:
    if precheck_error is not None:
        return "预检失败"
    status = str(result_payload.get("status", "failed"))
    if status == "success":
        return "全部完成"
    if status == "partial_success":
        return "部分完成"
    return "全部失败"


def _build_summary_email(
    cfg: SchedulerConfig,
    *,
    started_at: datetime,
    request_payload: dict[str, Any],
    result_payload: dict[str, Any],
    target_date: str,
    error_text: str | None,
    traceback_text: str | None,
    run_dir: Path,
    precheck_error: WechatConnectivityPrecheckError | None,
) -> tuple[str, str]:
    diagnostics = result_payload.get("diagnostics", {}) if isinstance(result_payload, dict) else {}
    modules = diagnostics.get("modules", {}) if isinstance(diagnostics, dict) else {}
    steps = diagnostics.get("steps", {}) if isinstance(diagnostics, dict) else {}

    label = _label_from_result(result_payload, precheck_error)
    subject = f"[微信发布总结][{label}][{target_date}]"

    arxiv_module = modules.get("arxiv", {}) if isinstance(modules.get("arxiv", {}), dict) else {}
    journal_module = modules.get("journal", {}) if isinstance(modules.get("journal", {}), dict) else {}
    wechat_step = steps.get("wechat_connectivity", {}) if isinstance(steps.get("wechat_connectivity", {}), dict) else {}
    draft_step = steps.get("draft_publish", {}) if isinstance(steps.get("draft_publish", {}), dict) else {}
    ai_step = steps.get("ai_enhance", {}) if isinstance(steps.get("ai_enhance", {}), dict) else {}
    git_step = steps.get("git_sync", {}) if isinstance(steps.get("git_sync", {}), dict) else {}
    xhs_step = steps.get("xiaohongshu_copy", {}) if isinstance(steps.get("xiaohongshu_copy", {}), dict) else {}
    xhs_payload = diagnostics.get("xiaohongshu_copy", {}) if isinstance(diagnostics.get("xiaohongshu_copy", {}), dict) else {}

    precheck_info: dict[str, Any] = {}
    if precheck_error is not None:
        precheck_info = precheck_error.to_dict()
    elif wechat_step:
        precheck_info = {
            "errcode": wechat_step.get("errcode"),
            "errmsg": wechat_step.get("errmsg", ""),
            "current_ip": wechat_step.get("current_ip"),
            "hinted_ip": wechat_step.get("hinted_ip"),
        }

    host_name = socket.gethostname()

    body = "\n".join(
        [
            "微信工作流运行总结",
            "",
            f"result_label: {label}",
            f"status: {result_payload.get('status', 'failed')}",
            f"target_date: {target_date}",
            f"started_at: {started_at.isoformat()}",
            f"finished_at: {_now(cfg.timezone_name).isoformat()}",
            f"dry_run: {request_payload.get('dry_run')}",
            f"run_arxiv_module: {request_payload.get('run_arxiv_module')}",
            f"run_journal_module: {request_payload.get('run_journal_module')}",
            f"host: {host_name}",
            f"run_dir: {run_dir.resolve()}",
            "",
            "模块状态:",
            f"- arxiv: {arxiv_module.get('status', 'unknown')}",
            f"- journal: {journal_module.get('status', 'unknown')}",
            "",
            "步骤状态:",
            f"- wechat_connectivity: {wechat_step.get('status', 'unknown')}",
            f"- draft_publish: {draft_step.get('status', 'unknown')}",
            f"- ai_enhance: {ai_step.get('status', 'unknown')}",
            f"- git_sync: {git_step.get('status', 'unknown')}",
            f"- xiaohongshu_copy: {xhs_step.get('status', 'unknown')}",
            "",
        ]
    )
    xhs_content = str(xhs_payload.get("content", "")).strip()
    if xhs_content:
        body += "\n".join(
            [
                "小红书文案正文:",
                xhs_content,
                "",
            ]
        )
    if precheck_info:
        body += "\n".join(
            [
                "预检详情:",
                f"- errcode: {precheck_info.get('errcode')}",
                f"- errmsg: {precheck_info.get('errmsg', '')}",
                f"- current_ip: {precheck_info.get('current_ip')}",
                f"- hinted_ip: {precheck_info.get('hinted_ip')}",
                "",
            ]
        )
    if error_text:
        body += "\n".join(["失败摘要:", error_text, ""])
    if traceback_text:
        body += "\n".join(["完整异常文本:", traceback_text.rstrip(), ""])
    return subject, body


def _send_summary_email(
    cfg: SchedulerConfig,
    *,
    started_at: datetime,
    request_payload: dict[str, Any],
    result_payload: dict[str, Any],
    target_date: str,
    error_text: str | None,
    traceback_text: str | None,
    run_dir: Path,
    precheck_error: WechatConnectivityPrecheckError | None,
) -> None:
    if not cfg.email_alert_config.enabled:
        return

    subject, body = _build_summary_email(
        cfg,
        started_at=started_at,
        request_payload=request_payload,
        result_payload=result_payload,
        target_date=target_date,
        error_text=error_text,
        traceback_text=traceback_text,
        run_dir=run_dir,
        precheck_error=precheck_error,
    )
    send_email(cfg.email_alert_config, subject, body)
    LOGGER.info(
        "运行总结邮件已发送 recipients=%s subject=%s",
        ",".join(cfg.email_alert_config.recipients),
        subject,
    )


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
    result_payload: dict[str, Any] | None = None
    error_text: str | None = None
    traceback_text: str | None = None
    caught_exception: Exception | None = None

    try:
        result_payload = run_wechat_publish_pipeline(
            date_set=target_date,
            dry_run=dry_run,
            run_arxiv_module=cfg.run_arxiv_module,
            run_journal_module=cfg.run_journal_module,
        )
        if str(result_payload.get("status")) == "failed":
            error_text = "pipeline returned failed status"
            caught_exception = RuntimeError(error_text)
        LOGGER.info(
            "发布任务完成 status=%s articles=%s draft_media_id=%s",
            result_payload.get("status"),
            result_payload.get("articles_count"),
            result_payload.get("draft_media_id"),
        )
    except Exception as exc:
        caught_exception = exc
        error_text = str(exc)
        traceback_text = traceback.format_exc()
        LOGGER.exception("发布任务失败")
        diagnostics = getattr(exc, "diagnostics", None)
        if not isinstance(diagnostics, dict):
            diagnostics = {}
        if isinstance(exc, WechatConnectivityPrecheckError):
            steps = diagnostics.setdefault("steps", {})
            steps["wechat_connectivity"] = {"status": "failed", **exc.to_dict()}
        result_payload = _failed_result_payload(target_date=target_date, diagnostics=diagnostics)
    finally:
        if result_payload is None:
            result_payload = _failed_result_payload(target_date=target_date, diagnostics={})

        run_dir = _record_run(cfg, started_at, request_payload, result_payload, error_text)

        precheck_error = (
            caught_exception if isinstance(caught_exception, WechatConnectivityPrecheckError) else None
        )
        try:
            _send_summary_email(
                cfg,
                started_at=started_at,
                request_payload=request_payload,
                result_payload=result_payload,
                target_date=target_date,
                error_text=error_text,
                traceback_text=traceback_text,
                run_dir=run_dir,
                precheck_error=precheck_error,
            )
        except Exception:
            LOGGER.exception("发送运行总结邮件失败")

    if caught_exception is not None:
        raise caught_exception
    return result_payload


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

    log_path, log_fp = _open_run_log_file(args)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _TeeStream(original_stdout, log_fp)
    sys.stderr = _TeeStream(original_stderr, log_fp)

    try:
        _setup_logging(args.log_level)
        LOGGER.info("日志文件: %s", log_path.resolve())
        _report_external_log_path(log_path)

        cfg = load_scheduler_config()

        if args.once:
            execute_once(cfg, date_set=args.date_set, dry_run=args.dry_run)
            return 0

        run_daemon(cfg, dry_run=args.dry_run)
        return 0
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_fp.close()


if __name__ == "__main__":
    sys.exit(main())
