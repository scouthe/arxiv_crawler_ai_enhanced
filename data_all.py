#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import sqlite3
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
import time

from run_crawler import crawl_only, ai_enhance_only


MONTH_CRAWL_RETRY_WAIT_SECONDS = 5 * 60
MONTH_CRAWL_MAX_RETRIES = 3
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "papers.db"


def _parse_date(raw: str) -> date:
    return date.fromisoformat(raw)


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _next_month(day: date) -> date:
    if day.month == 12:
        return day.replace(year=day.year + 1, month=1, day=1)
    return day.replace(month=day.month + 1, day=1)


def _iter_month_starts(start_day: date, end_day: date):
    current = _month_start(start_day)
    while current <= end_day:
        yield current
        current = _next_month(current)


def _iter_days_in_month(month_start: date, start_day: date, end_day: date):
    days_in_month = monthrange(month_start.year, month_start.month)[1]
    month_end = month_start.replace(day=days_in_month)
    current = max(month_start, start_day)
    last = min(month_end, end_day)
    while current <= last:
        yield current
        current += timedelta(days=1)


def _is_weekday(day: date) -> bool:
    return day.weekday() < 5


def _iter_weekdays_in_month(month_start: date, start_day: date, end_day: date):
    for current in _iter_days_in_month(month_start, start_day, end_day):
        if _is_weekday(current):
            yield current


def _connect_papers_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"papers.db 不存在: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _load_dates_with_papers(db_path: Path, start_day: date, end_day: date) -> set[date]:
    with _connect_papers_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT first_announced_date
            FROM papers
            WHERE first_announced_date BETWEEN ? AND ?
            """,
            (start_day.isoformat(), end_day.isoformat()),
        ).fetchall()

    dates = set()
    for row in rows:
        raw_date = str(row["first_announced_date"] or "").strip()
        if not raw_date:
            continue
        try:
            dates.add(date.fromisoformat(raw_date[:10]))
        except ValueError:
            print(f"忽略无法解析的 first_announced_date: {raw_date}")
    return dates


def _missing_days(days: list[date], dates_with_papers: set[date]) -> list[date]:
    return [day for day in days if day not in dates_with_papers]


def _format_days(days: list[date], max_items: int = 8) -> str:
    if not days:
        return "无"
    preview = ", ".join(day.isoformat() for day in days[:max_items])
    if len(days) > max_items:
        preview += f", ... 共 {len(days)} 天"
    return preview


def _crawl_month_with_retries(month_str: str) -> bool:
    total_attempts = MONTH_CRAWL_MAX_RETRIES + 1

    for attempt in range(1, total_attempts + 1):
        print(f"整月抓取尝试 {attempt}/{total_attempts}：{month_str}")
        success = crawl_only(True, month_str)
        if success:
            return True

        if attempt < total_attempts:
            wait_minutes = MONTH_CRAWL_RETRY_WAIT_SECONDS // 60
            print(
                f"整月抓取失败：{month_str}。"
                f" {wait_minutes} 分钟后进行下一次重试..."
            )
            time.sleep(MONTH_CRAWL_RETRY_WAIT_SECONDS)

    print(f"本月论文抓取失败：{month_str}")
    return False


def run_all_data(start_date: str, end_date: str, db_path: str | Path = DEFAULT_DB_PATH, force_crawl: bool = False) -> bool:
    start_day = _parse_date(start_date)
    end_day = _parse_date(end_date)
    if start_day > end_day:
        raise ValueError(f"start_date must be <= end_date: {start_date} > {end_date}")

    db_path = Path(db_path).expanduser().resolve()

    month_starts = list(_iter_month_starts(start_day, end_day))
    failed_months = []
    print(f"开始批量处理：{start_day} -> {end_day}，共 {len(month_starts)} 个月")
    print(f"读取数据库：{db_path}")

    for month_index, month_start in enumerate(month_starts, start=1):
        month_str = month_start.strftime('%Y-%m-%d')
        month_days = list(_iter_weekdays_in_month(month_start, start_day, end_day))
        if not month_days:
            print()
            print(f"[{month_index}/{len(month_starts)}] 跳过月份：{month_str}（范围内只有周六周天）")
            continue

        month_end = month_days[-1]

        print()
        print(f"[{month_index}/{len(month_starts)}] 检查月份：{month_str}")

        dates_with_papers = _load_dates_with_papers(db_path, month_days[0], month_end)
        missing_before_crawl = _missing_days(month_days, dates_with_papers)
        print(
            f"本月工作日范围 {month_days[0]} -> {month_end}："
            f"已有数据 {len(month_days) - len(missing_before_crawl)} 天，"
            f"空数据 {len(missing_before_crawl)} 天"
        )
        print(f"空数据工作日：{_format_days(missing_before_crawl)}")

        should_crawl = force_crawl or bool(missing_before_crawl)
        if should_crawl:
            reason = "强制抓取" if force_crawl else "存在空数据日期"
            print(f"开始整月抓取：{month_str}（{reason}）")
            success = _crawl_month_with_retries(month_str)
            if not success:
                failed_months.append(month_str)
                print(f"跳过本月 AI 增强：{month_str}（本月抓取失败）")
                continue

            dates_with_papers = _load_dates_with_papers(db_path, month_days[0], month_end)
        else:
            print(f"跳过整月抓取：{month_str}（本月日期均已有论文数据）")

        if force_crawl:
            days_to_enhance = [day for day in month_days if day in dates_with_papers]
        else:
            days_to_enhance = [day for day in missing_before_crawl if day in dates_with_papers]

        still_empty_days = _missing_days(missing_before_crawl, dates_with_papers)
        if still_empty_days:
            print(f"抓取后仍无论文数据，跳过 AI 增强：{_format_days(still_empty_days)}")

        if not days_to_enhance:
            print(f"本月没有需要 AI 增强的新增日期：{month_str}")
            continue

        for day_index, current_day in enumerate(days_to_enhance, start=1):
            day_str = current_day.strftime('%Y-%m-%d')
            print(f"  - [{day_index}/{len(days_to_enhance)}] AI增强：{day_str}")
            success = ai_enhance_only(day_str)
            if not success:
                print(f"AI增强失败：{day_str}")
                return False

    print()
    if failed_months:
        print("批量处理完成，但以下月份抓取失败：")
        for failed_month in failed_months:
            print(f"- {failed_month}")
        return False

    print("全部处理完成！")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="按月抓取、按天AI增强历史论文数据")
    parser.add_argument('--start-date', default='2021-04-26', help='开始日期，格式 YYYY-MM-DD')
    parser.add_argument('--end-date', default='2021-07-31', help='结束日期，格式 YYYY-MM-DD')
    parser.add_argument('--db-path', default=str(DEFAULT_DB_PATH), help='papers.db 路径')
    parser.add_argument('--force-crawl', action='store_true', help='忽略数据库检查，恢复为每个月都抓取')

    args = parser.parse_args()
    success = run_all_data(args.start_date, args.end_date, db_path=args.db_path, force_crawl=args.force_crawl)
    sys.exit(0 if success else 1)
