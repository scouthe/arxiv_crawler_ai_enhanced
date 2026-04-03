import json
import re
from pathlib import Path

from .models import DraftArticle


def _safe_stem(text: str, max_len: int = 80) -> str:
    normalized = re.sub(r"\s+", "_", text.strip())
    normalized = re.sub(r'[\\/:*?"<>|]', "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("._")
    if not normalized:
        normalized = "article"
    return normalized[:max_len]


def _clear_previous_export(export_dir: Path) -> None:
    for pattern in ("*.content.html", "*.payload.json", "manifest.json"):
        for path in export_dir.glob(pattern):
            path.unlink(missing_ok=True)


def export_articles(date_str: str, articles: list[DraftArticle], output_root: Path) -> dict:
    export_dir = output_root / date_str
    export_dir.mkdir(parents=True, exist_ok=True)
    _clear_previous_export(export_dir)

    manifest: list[dict] = []
    for idx, article in enumerate(articles, start=1):
        stem = f"{idx:02d}_{_safe_stem(article.title)}"
        content_file = export_dir / f"{stem}.content.html"
        payload_file = export_dir / f"{stem}.payload.json"

        content_file.write_text(article.content, encoding="utf-8")
        payload = article.to_dict()
        payload_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        manifest.append(
            {
                "index": idx,
                "title": article.title,
                "digest": article.digest,
                "content_file": content_file.name,
                "payload_file": payload_file.name,
            }
        )

    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "date": date_str,
                "articles_count": len(articles),
                "articles": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "status": "success",
        "export_dir": str(export_dir.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "articles_count": len(articles),
    }
