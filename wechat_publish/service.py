from .orchestrator import load_config, run_pipeline


def run_wechat_publish_pipeline(
    date_set: str | None = None,
    dry_run: bool = False,
    run_arxiv_module: bool = True,
    run_journal_module: bool = True,
) -> dict:
    config = load_config(date_set)
    result = run_pipeline(
        config=config,
        dry_run=dry_run,
        run_arxiv_module=run_arxiv_module,
        run_journal_module=run_journal_module,
    )
    return {
        "status": result.status,
        "date": result.date,
        "articles_count": result.articles_count,
        "draft_media_id": result.draft_media_id,
        "article_titles": result.article_titles,
        "diagnostics": result.diagnostics,
    }
