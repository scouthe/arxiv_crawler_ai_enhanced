import os
import time
from datetime import date
from pathlib import Path

from run_crawler import ai_enhance_only, crawl_only

from git_sync import run_git_sync_internal

from .journal_branch import build_journal_article, load_journal_assets
from .markdown_branches import build_three_arxiv_articles
from .models import DraftArticle, PipelineConfig, PublishResult
from .wechat_client import WechatClient


def _truncate_wechat_title(title: str, max_bytes: int = 60) -> str:
    if len(title.encode("utf-8")) <= max_bytes:
        return title
    suffix = "..."
    suffix_bytes = len(suffix.encode("utf-8"))
    budget = max(1, max_bytes - suffix_bytes)
    cur = title
    while cur and len(cur.encode("utf-8")) > budget:
        cur = cur[:-1]
    if not cur:
        return suffix[:max_bytes]
    return cur + suffix


def load_config(date_str: str | None = None) -> PipelineConfig:
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")
    return PipelineConfig(
        date_str=date_str,
        markdown_dir=Path(os.environ.get("WECHAT_MARKDOWN_DIR", "./to_md/markdown")),
        assets_dir=Path(os.environ.get("WECHAT_ASSETS_DIR", "./wechat_assets")),
        wait_minutes=int(os.environ.get("WECHAT_WAIT_MINUTES", "30")),
        wait_retries=int(os.environ.get("WECHAT_WAIT_RETRIES", "1")),
        draft_author=os.environ.get("WECHAT_DRAFT_AUTHOR", "tianhe"),
        content_source_url=os.environ.get("WECHAT_CONTENT_SOURCE_URL", "https://scouthe.github.io/arxiv_crawler_ai_enhanced/"),
        thumb_id_arxiv_main=os.environ.get(
            "WECHAT_THUMB_ID_ARXIV_MAIN",
            "H1msZTrDz2EEoa3-9SwY7nYgsGEPu-9nbzP4p9Ji_slq23ayzKs61aMcUm8YLCsu",
        ),
        thumb_id_arxiv_audio=os.environ.get(
            "WECHAT_THUMB_ID_ARXIV_AUDIO",
            "H1msZTrDz2EEoa3-9SwY7ujfXS7JGySdfP02DFW2Y8ODyQ2zzQz128iFo2bLRpgi",
        ),
        thumb_id_arxiv_hc_ro=os.environ.get(
            "WECHAT_THUMB_ID_ARXIV_HC_RO",
            "H1msZTrDz2EEoa3-9SwY7tpx7hIOh8ylNs2mMIxat-cEjqnIqEsEpP6snBAnufuL",
        ),
        thumb_id_journal=os.environ.get("WECHAT_THUMB_ID_JOURNAL", ""),
        wechat_app_id=os.environ.get("WECHAT_APP_ID", ""),
        wechat_app_secret=os.environ.get("WECHAT_APP_SECRET", ""),
    )


def _read_markdown_with_retry(config: PipelineConfig) -> str:
    md_file = config.markdown_dir / f"{config.date_str}.md"
    crawl_only(all=False, date_set=config.date_str)

    for attempt in range(config.wait_retries + 1):
        if md_file.exists():
            content = md_file.read_text(encoding="utf-8")
            if content.strip():
                return content
        if attempt < config.wait_retries:
            time.sleep(config.wait_minutes * 60)
            crawl_only(all=False, date_set=config.date_str)
    raise RuntimeError(f"markdown not ready: {md_file}")


def _build_articles(
    config: PipelineConfig,
    markdown_text: str,
    dry_run: bool,
    run_arxiv_module: bool,
    run_journal_module: bool,
) -> tuple[list[DraftArticle], dict]:
    if not run_arxiv_module and not run_journal_module:
        raise RuntimeError("run_arxiv_module 和 run_journal_module 不能同时为 false")

    articles: list[DraftArticle] = []
    diagnostics: dict = {}

    if run_arxiv_module:
        arxiv_articles, arxiv_diag = build_three_arxiv_articles(
            markdown_text=markdown_text,
            date_str=config.date_str,
            author=config.draft_author,
            source_url=config.content_source_url,
            thumb_main=config.thumb_id_arxiv_main,
            thumb_audio=config.thumb_id_arxiv_audio,
            thumb_hcro=config.thumb_id_arxiv_hc_ro,
        )
        articles.extend(arxiv_articles)
        diagnostics["arxiv"] = arxiv_diag

    if run_journal_module:
        md_files, png_files = load_journal_assets(config.assets_dir, config.date_str)
        md_texts = [x.read_text(encoding="utf-8") for x in md_files]

        journal_thumb_media_id = config.thumb_id_journal
        if dry_run:
            image_urls = [f"https://example.com/mock-{i}.png" for i, _ in enumerate(png_files)]
            if not journal_thumb_media_id and len(png_files) > 4:
                journal_thumb_media_id = "MOCK_MEDIA_ID_INDEX_4"
        else:
            if not config.wechat_app_id or not config.wechat_app_secret:
                raise RuntimeError("WECHAT_APP_ID/WECHAT_APP_SECRET is required when dry_run=false")
            client = WechatClient(config.wechat_app_id, config.wechat_app_secret)
            uploaded = [client.upload_image_material(path) for path in png_files]
            image_urls = [item.get("url", "") for item in uploaded]
            if not journal_thumb_media_id and len(uploaded) > 4:
                journal_thumb_media_id = uploaded[4].get("media_id", "")

        journal_article = build_journal_article(
            markdown_items=md_texts,
            image_urls=image_urls,
            author=config.draft_author,
            thumb_media_id=journal_thumb_media_id,
        )
        # 期刊介绍固定放第一位
        articles = [journal_article] + articles
        diagnostics["journal"] = {
            "md_count": len(md_files),
            "png_count": len(png_files),
            "image_url_count": len(image_urls),
        }

    if len(articles) > 8:
        articles = articles[:8]

    return articles, diagnostics


def run_pipeline(
    config: PipelineConfig,
    dry_run: bool = False,
    run_arxiv_module: bool = True,
    run_journal_module: bool = True,
) -> PublishResult:
    markdown_text = _read_markdown_with_retry(config)
    articles, diagnostics = _build_articles(
        config,
        markdown_text,
        dry_run=dry_run,
        run_arxiv_module=run_arxiv_module,
        run_journal_module=run_journal_module,
    )
    title_max_bytes = int(os.environ.get("WECHAT_TITLE_MAX_BYTES", "0"))
    if title_max_bytes > 0:
        for article in articles:
            article.title = _truncate_wechat_title(article.title, max_bytes=title_max_bytes)

    draft_media_id = None
    if not dry_run:
        client = WechatClient(config.wechat_app_id, config.wechat_app_secret)
        draft_resp = client.add_draft([a.to_dict() for a in articles])
        draft_media_id = draft_resp.get("media_id")

    ai_enhance_only(date_set=config.date_str)

    diagnostics["git_sync"] = run_git_sync_internal(today_str=config.date_str)

    return PublishResult(
        status="success",
        date=config.date_str,
        articles_count=len(articles),
        article_titles=[a.title for a in articles],
        draft_media_id=draft_media_id,
        diagnostics=diagnostics,
    )
