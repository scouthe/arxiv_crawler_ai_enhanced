#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import importlib.util
import json
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
DEFAULT_LANGUAGE = "Chinese"
DEFAULT_CLOUDBASE_DEMO_DIR = WORKSPACE_ROOT / "cloudbase_db_demo"


def _resolve_project_path(raw_path: str | None, default: str) -> Path:
    path = Path(raw_path or default).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def get_daily_jsonl_dir() -> Path:
    raw_dir = os.environ.get("DAILY_JSONL_DIR") or os.environ.get("IMPORT_JSONL_DIR")
    return _resolve_project_path(raw_dir, "data/daily")


def _resolve_cloudbase_demo_dir(raw_path: str | None = None) -> Path:
    path = Path(raw_path or os.environ.get("CLOUDBASE_DEMO_DIR") or DEFAULT_CLOUDBASE_DEMO_DIR).expanduser()
    if path.is_absolute():
        return path
    return WORKSPACE_ROOT / path


def _load_cloudbase_demo_module(demo_dir: Path):
    demo_path = demo_dir / "demo.py"
    if not demo_path.exists():
        raise FileNotFoundError(f"CloudBase demo.py 不存在: {demo_path}")

    demo_dir_str = str(demo_dir)
    if demo_dir_str not in sys.path:
        sys.path.insert(0, demo_dir_str)

    spec = importlib.util.spec_from_file_location("cloudbase_db_demo_import", demo_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 CloudBase demo 模块: {demo_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upload_daily_jsonl_to_cloudbase(
    jsonl_path: Path,
    table: str | None = None,
    limit: int | None = None,
    demo_dir: Path | None = None,
) -> dict:
    demo_dir = demo_dir or _resolve_cloudbase_demo_dir()
    load_dotenv(demo_dir / ".env", override=False)

    demo = _load_cloudbase_demo_module(demo_dir)
    client = demo.CloudBaseClient()
    table_name = table or os.environ.get("CLOUDBASE_TABLE") or os.environ.get("DEFAULT_TABLE") or "papers"
    return demo.import_jsonl(client, table_name, jsonl_path, limit)


def update_papers_meta_in_cloudbase(
    date_str: str | None = None,
    demo_dir: Path | None = None,
) -> dict:
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")

    demo_dir = demo_dir or _resolve_cloudbase_demo_dir()
    load_dotenv(demo_dir / ".env", override=False)

    demo = _load_cloudbase_demo_module(demo_dir)
    client = demo.CloudBaseClient()
    return client.update_papers_meta(action="update", date=date_str)


def _load_jsonl_records(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path} 第 {line_no} 行不是合法 JSON: {exc}") from exc
    return records


def _split_text_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in re.split(r",\s*", raw_value) if item.strip()]


def _normalize_authors(raw_authors, fallback_text: str | None) -> tuple[list[str], str]:
    if isinstance(raw_authors, list):
        authors = [str(author).strip() for author in raw_authors if str(author).strip()]
    elif isinstance(raw_authors, str):
        authors = _split_text_list(raw_authors)
    else:
        authors = []

    fallback_authors = _split_text_list(fallback_text)
    if not authors:
        authors = fallback_authors

    authors_text = fallback_text or ", ".join(authors)
    if authors_text == "No authors":
        authors_text = ""
    return authors, authors_text


def _normalize_categories(raw_categories, fallback_text: str | None) -> tuple[list[str], str]:
    if isinstance(raw_categories, list):
        categories = [str(category).strip() for category in raw_categories if str(category).strip()]
    elif isinstance(raw_categories, str):
        categories = _split_text_list(raw_categories)
    else:
        categories = []

    fallback_categories = _split_text_list(fallback_text)
    if not categories:
        categories = fallback_categories
    return categories, fallback_text or ",".join(categories)


def _parse_ai_content(raw_ai_content: str | None, fallback_ai: dict | None) -> dict:
    if raw_ai_content:
        try:
            parsed = json.loads(raw_ai_content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return fallback_ai or {}


def _nullable_comment(raw_comment: str | None) -> str | None:
    if not raw_comment or raw_comment == "No comments":
        return None
    return raw_comment


def export_daily_jsonl(
    date_str: str | None = None,
    language: str = DEFAULT_LANGUAGE,
    output_dir: Path | None = None,
    db_path: Path | None = None,
    source_file: Path | None = None,
) -> tuple[Path, int]:
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")

    db_path = db_path or PROJECT_ROOT / "papers.db"
    source_file = source_file or PROJECT_ROOT / "data" / f"{date_str}_AI_enhanced_{language}.jsonl"
    output_dir = output_dir or get_daily_jsonl_dir()
    output_path = output_dir / f"{date_str}.jsonl"

    if not source_file.exists():
        raise FileNotFoundError(f"AI 增强 JSONL 不存在: {source_file}")
    if not db_path.exists():
        raise FileNotFoundError(f"papers.db 不存在: {db_path}")

    enhanced_records = _load_jsonl_records(source_file)
    if not enhanced_records:
        print(f"AI 增强 JSONL 为空: {source_file}")
        return output_path, 0
    
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            for record in enhanced_records:
                paper_id = str(record.get("id") or "").strip()
                if not paper_id:
                    raise RuntimeError(f"存在缺少 id 的记录: {source_file}")

                db_row = conn.execute(
                    """
                    SELECT id, url, pdf, authors, title_translated, first_submitted_date,
                           first_announced_date, update_time, categories, title, comments,
                           abstract, summary, abstract_translated, ai_content
                    FROM papers
                    WHERE id = ?
                    """,
                    (paper_id,),
                ).fetchone()
                if db_row is None:
                    raise RuntimeError(f"papers.db 中找不到论文: {paper_id}")

                ai_content = _parse_ai_content(db_row["ai_content"], record.get("AI"))
                authors, authors_text = _normalize_authors(record.get("authors"), db_row["authors"])
                categories, categories_text = _normalize_categories(record.get("categories"), db_row["categories"])
                abstract = db_row["abstract"] or record.get("summary") or ""
                summary = db_row["summary"] or record.get("summary") or abstract
                title = db_row["title"] or record.get("title") or ""
                title_zh = db_row["title_translated"] or record.get("title_zh") or ""
                abstract_zh = db_row["abstract_translated"] or record.get("abstract_zh") or ""
                comments = _nullable_comment(db_row["comments"] or record.get("comment"))

                daily_record = {
                    "id": paper_id,
                    "url": db_row["url"] or record.get("abs") or "",
                    "abs": db_row["url"] or record.get("abs") or "",
                    "pdf": db_row["pdf"] or record.get("pdf") or "",
                    "authors": authors,
                    "authors_json": authors,
                    "authors_text": authors_text,
                    "title": title,
                    "title_zh": title_zh,
                    "first_submitted_date": db_row["first_submitted_date"],
                    "first_announced_date": db_row["first_announced_date"],
                    "update_time": db_row["update_time"],
                    "categories": categories,
                    "categories_text": categories_text,
                    "comment": comments,
                    "comments": comments,
                    "abstract": abstract,
                    "summary": summary,
                    "abstract_zh": abstract_zh,
                    "AI": ai_content,
                    "ai_content": ai_content,
                    "ai_content_json": ai_content,
                    "tldr": ai_content.get("tldr", ""),
                    "motivation": ai_content.get("motivation", ""),
                    "method": ai_content.get("method", ""),
                    "result": ai_content.get("result", ""),
                    "conclusion": ai_content.get("conclusion", ""),
                    "search_text": " ".join(
                        filter(
                            None,
                            [
                                title,
                                title_zh,
                                abstract,
                                abstract_zh,
                                ai_content.get("tldr", ""),
                                authors_text,
                                categories_text,
                            ],
                        )
                    ),
                }
                file.write(json.dumps(daily_record, ensure_ascii=False) + "\n")
    finally:
        conn.close()

    temp_path.replace(output_path)
    return output_path, len(enhanced_records)


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description="导出云端导入服务使用的每日 JSONL")
    parser.add_argument("--date", dest="date_str", default=None, help="日期，格式 YYYY-MM-DD，默认今天")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="AI 增强文件语言后缀，默认 Chinese")
    parser.add_argument("--output-dir", default=None, help="输出目录，默认 DAILY_JSONL_DIR/IMPORT_JSONL_DIR/data/daily")
    parser.add_argument("--upload", action="store_true", help="导出后上传到 CloudBase 数据库")
    parser.add_argument("--table", default=None, help="CloudBase 表名，默认 CLOUDBASE_TABLE/DEFAULT_TABLE/papers")
    parser.add_argument("--limit", type=int, default=None, help="上传记录数限制，用于小批量测试")
    parser.add_argument("--cloudbase-demo-dir", default=None, help="cloudbase_db_demo 目录，默认相邻目录")
    parser.add_argument("--skip-meta", action="store_true", help="上传后不更新 CloudBase papers_meta")
    args = parser.parse_args()

    target_date = args.date_str or date.today().strftime("%Y-%m-%d")

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    output_path, count = export_daily_jsonl(
        date_str=target_date,
        language=args.language,
        output_dir=output_dir,
    )
    print(f"已生成每日导入 JSONL: {output_path}，共 {count} 条")
    if args.upload:
        if count <= 0:
            print("每日导入 JSONL 为空，跳过 CloudBase 上传")
            return 0
        upload_result = upload_daily_jsonl_to_cloudbase(
            output_path,
            table=args.table,
            limit=args.limit,
            demo_dir=_resolve_cloudbase_demo_dir(args.cloudbase_demo_dir),
        )
        print("已上传 CloudBase:")
        print(json.dumps(upload_result, ensure_ascii=False, indent=2))
        if not args.skip_meta and args.limit is not None:
            print("已设置 --limit，跳过 papers_meta 更新")
        elif not args.skip_meta and upload_result.get("failed", 0) == 0:
            meta_result = update_papers_meta_in_cloudbase(
                target_date,
                demo_dir=_resolve_cloudbase_demo_dir(args.cloudbase_demo_dir),
            )
            print("已更新 CloudBase papers_meta:")
            print(json.dumps(meta_result, ensure_ascii=False, indent=2))
        elif not args.skip_meta:
            print("CloudBase 上传存在失败记录，跳过 papers_meta 更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
