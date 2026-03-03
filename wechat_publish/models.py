from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PaperCardData:
    english_title: str = ""
    chinese_title: str = ""
    arxiv_link: str = ""
    authors: str = ""
    notes: str = "No Notes"
    chinese_abstract: str = ""
    english_abstract: str = ""
    category_html: str = ""
    stats: dict[str, int] = field(default_factory=dict)


@dataclass
class DraftArticle:
    title: str
    author: str
    digest: str
    show_cover_pic: int
    content: str
    thumb_media_id: str
    need_open_comment: int = 1
    content_source_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "title": self.title,
            "author": self.author,
            "digest": self.digest,
            "show_cover_pic": self.show_cover_pic,
            "content": self.content,
            "thumb_media_id": self.thumb_media_id,
            "need_open_comment": self.need_open_comment,
        }
        if self.content_source_url:
            payload["content_source_url"] = self.content_source_url
        return payload


@dataclass
class PublishResult:
    status: str
    date: str
    articles_count: int
    article_titles: list[str]
    draft_media_id: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    date_str: str
    markdown_dir: Path
    assets_dir: Path
    wait_minutes: int
    wait_retries: int
    draft_author: str
    content_source_url: str
    thumb_id_arxiv_main: str
    thumb_id_arxiv_audio: str
    thumb_id_arxiv_hc_ro: str
    thumb_id_journal: str
    wechat_app_id: str
    wechat_app_secret: str

