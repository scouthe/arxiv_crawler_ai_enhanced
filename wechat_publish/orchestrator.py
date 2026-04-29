import os
import time
import logging
from datetime import date
from pathlib import Path

from run_crawler import ai_enhance_only, crawl_only

from git_sync import run_git_sync_internal

from .chart import generate_charts_from_config
from .journal_branch import (
    DEFAULT_BRAND_LOGO_PATH,
    build_journal_article,
    load_journal_assets,
)
from .markdown_branches import build_three_arxiv_articles
from .models import (
    DraftArticle,
    PipelineConfig,
    PublishResult,
    WechatConnectivityPrecheckError,
)
from .wechat_client import WechatClient, WechatAPIError, get_public_ip
from .xiaohongshu_copy import generate_xiaohongshu_copy_from_journal


LOGGER = logging.getLogger("wechat_publish.orchestrator")


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


def _set_article_titles(articles: list[DraftArticle], titles: list[str]) -> None:
    for article, title in zip(articles, titles):
        article.title = title


def _title_retry_limits(configured_limit: int) -> list[int]:
    limits: list[int] = []
    if configured_limit > 0:
        limits.append(configured_limit)
    for limit in (140, 128, 120, 112, 104, 96, 88, 80, 72, 64, 60, 56, 52, 48):
        if limit not in limits:
            limits.append(limit)
    return limits


def _retry_add_draft_with_safe_titles(
    client: WechatClient,
    articles: list[DraftArticle],
    base_titles: list[str],
    configured_limit: int,
) -> dict:
    last_exc: WechatAPIError | None = None
    last_titles = [article.title for article in articles]

    for limit in _title_retry_limits(configured_limit):
        retry_titles = [_truncate_wechat_title(title, max_bytes=limit) for title in base_titles]
        if retry_titles == last_titles:
            continue

        _set_article_titles(articles, retry_titles)
        LOGGER.warning("微信草稿标题超限，使用 %s bytes 截断后重试上传", limit)
        for idx, (before, after) in enumerate(zip(base_titles, retry_titles), start=1):
            if before != after:
                LOGGER.info("标题截断 article=%s before=%s after=%s", idx, before, after)

        try:
            return client.add_draft([article.to_dict() for article in articles])
        except WechatAPIError as exc:
            last_exc = exc
            last_titles = retry_titles
            if exc.errcode != 45003:
                raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("title retry requested but no retry candidates were available")


def _cleanup_markdown_file(md_file: Path) -> None:
    """Remove transient markdown after use; it will be regenerated on next run."""
    try:
        md_file.unlink(missing_ok=True)
    except Exception:
        # Best-effort cleanup only.
        pass


def _preflight_wechat_connectivity(config: PipelineConfig) -> dict:
    if not config.wechat_app_id or not config.wechat_app_secret:
        raise WechatConnectivityPrecheckError(
            "WECHAT_APP_ID/WECHAT_APP_SECRET is required when dry_run=false",
            errmsg="missing wechat app credentials",
            current_ip=get_public_ip() or "unknown",
        )

    client = WechatClient(config.wechat_app_id, config.wechat_app_secret)
    try:
        client.get_access_token(force_refresh=True)
        return {"current_ip": get_public_ip() or "unknown"}
    except WechatAPIError as exc:
        current_ip = get_public_ip() or "unknown"
        hinted_ip = exc.hinted_ip
        if exc.is_ip_whitelist_error:
            message = (
                f"微信接口连通性预检失败：疑似 IP 白名单限制。"
                f" errcode={exc.errcode}, errmsg={exc.errmsg}, 当前公网IP={current_ip}"
            )
            if hinted_ip:
                message += f", 微信返回IP={hinted_ip}"
            message += "。请将该IP加入白名单后重试。"
            LOGGER.error(message)
            raise WechatConnectivityPrecheckError(
                message,
                errcode=exc.errcode,
                errmsg=exc.errmsg,
                current_ip=current_ip,
                hinted_ip=hinted_ip,
                raw_data=exc.data,
            ) from exc

        message = (
            f"微信接口连通性预检失败。 errcode={exc.errcode}, errmsg={exc.errmsg}, 当前公网IP={current_ip}"
        )
        if hinted_ip:
            message += f", 微信返回IP={hinted_ip}"
        LOGGER.error(message)
        raise WechatConnectivityPrecheckError(
            message,
            errcode=exc.errcode,
            errmsg=exc.errmsg,
            current_ip=current_ip,
            hinted_ip=hinted_ip,
            raw_data=exc.data,
        ) from exc
    except Exception as exc:
        current_ip = get_public_ip() or "unknown"
        message = f"微信接口连通性预检失败: {exc}"
        LOGGER.error(message)
        raise WechatConnectivityPrecheckError(
            message,
            errmsg=str(exc),
            current_ip=current_ip,
            raw_data={"exception": str(exc)},
        ) from exc


def load_config(date_str: str | None = None) -> PipelineConfig:
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")
    return PipelineConfig(
        date_str=date_str,
        markdown_dir=Path(os.environ.get("WECHAT_MARKDOWN_DIR", "./to_md/markdown")),
        assets_dir=Path(os.environ.get("WECHAT_ASSETS_DIR", "./期刊介绍")),
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
                _cleanup_markdown_file(md_file)
                return content
        if attempt < config.wait_retries:
            time.sleep(config.wait_minutes * 60)
            crawl_only(all=False, date_set=config.date_str)
    raise RuntimeError(f"markdown not ready: {md_file}")


def _init_diagnostics(
    *,
    run_arxiv_module: bool,
    run_journal_module: bool,
    dry_run: bool,
) -> dict:
    modules: dict[str, dict] = {
        "arxiv": {"status": "pending"} if run_arxiv_module else {"status": "skipped", "reason": "disabled"},
        "journal": {"status": "pending"} if run_journal_module else {"status": "skipped", "reason": "disabled"},
    }
    steps: dict[str, dict] = {
        "wechat_connectivity": {"status": "pending"} if not dry_run else {"status": "skipped", "reason": "dry_run"},
        "draft_publish": {"status": "pending"},
        "ai_enhance": {"status": "pending"},
        "git_sync": {"status": "pending"},
        "xiaohongshu_copy": {"status": "pending"},
    }
    return {"modules": modules, "steps": steps}


def _raise_with_diagnostics(message: str, diagnostics: dict) -> None:
    exc = RuntimeError(message)
    setattr(exc, "diagnostics", diagnostics)
    raise exc


def run_pipeline(
    config: PipelineConfig,
    dry_run: bool = False,
    run_arxiv_module: bool = True,
    run_journal_module: bool = True,
) -> PublishResult:
    if not run_arxiv_module and not run_journal_module:
        raise RuntimeError("run_arxiv_module 和 run_journal_module 不能同时为 false")

    diagnostics = _init_diagnostics(
        run_arxiv_module=run_arxiv_module,
        run_journal_module=run_journal_module,
        dry_run=dry_run,
    )

    articles: list[DraftArticle] = []
    arxiv_success = False
    journal_success = False
    journal_markdown_for_xhs = ""

    if not dry_run:
        try:
            connectivity = _preflight_wechat_connectivity(config)
            diagnostics["steps"]["wechat_connectivity"] = {"status": "success", **connectivity}
        except WechatConnectivityPrecheckError as exc:
            diagnostics["steps"]["wechat_connectivity"] = {
                "status": "failed",
                **exc.to_dict(),
            }
            diagnostics["wechat_connectivity"] = diagnostics["steps"]["wechat_connectivity"]
            setattr(exc, "diagnostics", diagnostics)
            raise
    diagnostics["wechat_connectivity"] = diagnostics["steps"]["wechat_connectivity"]

    if run_arxiv_module:
        md_file = config.markdown_dir / f"{config.date_str}.md"
        try:
            markdown_text = _read_markdown_with_retry(config)
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
            diagnostics["modules"]["arxiv"] = {"status": "success", **arxiv_diag}
            diagnostics["arxiv"] = arxiv_diag
            arxiv_success = True
        except Exception as exc:
            diagnostics["modules"]["arxiv"] = {"status": "failed", "error": str(exc)}
            LOGGER.exception("论文模块执行失败")
        finally:
            _cleanup_markdown_file(md_file)

    if run_journal_module:
        try:
            md_files, png_files = load_journal_assets(config.assets_dir, config.date_str)
            md_texts = [x.read_text(encoding="utf-8") for x in md_files]
            journal_markdown_for_xhs = "\n\n".join(md_texts)
            journal_day_dir = md_files[0].parent
            chart_config_path = journal_day_dir / "chart_config.json"
            journal_cover_path = journal_day_dir / "cover.png"
            generated_chart_paths: dict[str, Path] = {}
            if chart_config_path.exists():
                generated_chart_paths = generate_charts_from_config(
                    chart_config_path,
                    journal_day_dir / "_generated",
                    journal_day_dir / "xhs",
                )
            else:
                LOGGER.info("未找到 chart_config.json，跳过期刊图表生成: %s", chart_config_path)

            journal_thumb_media_id = config.thumb_id_journal or config.thumb_id_arxiv_main
            brand_logo_url = ""
            image_map: dict[str, str] = {}
            original_png_paths = list(png_files)
            if dry_run:
                for i, path in enumerate(original_png_paths):
                    mock_url = f"https://example.com/mock-{i}.png"
                    image_map[path.name] = mock_url
                    image_map[path.stem] = mock_url
                for i, chart_name in enumerate(generated_chart_paths, start=len(original_png_paths)):
                    image_map[chart_name] = f"https://example.com/mock-chart-{i}.png"
                if DEFAULT_BRAND_LOGO_PATH.exists():
                    brand_logo_url = "https://example.com/mock-brand-logo.png"
                if journal_cover_path.exists():
                    journal_thumb_media_id = "MOCK_MEDIA_ID_COVER"
                elif not journal_thumb_media_id and len(original_png_paths) > 4:
                    journal_thumb_media_id = "MOCK_MEDIA_ID_INDEX_4"
            else:
                if not config.wechat_app_id or not config.wechat_app_secret:
                    raise RuntimeError("WECHAT_APP_ID/WECHAT_APP_SECRET is required when dry_run=false")
                client = WechatClient(config.wechat_app_id, config.wechat_app_secret)
                if DEFAULT_BRAND_LOGO_PATH.exists():
                    try:
                        brand_logo_upload = client.upload_image_material(DEFAULT_BRAND_LOGO_PATH)
                        brand_logo_url = brand_logo_upload.get("url", "")
                    except Exception:
                        LOGGER.exception("品牌 logo 上传失败，将继续生成无 logo 的期刊文章")

                uploaded_original = [
                    (path, client.upload_image_material(path))
                    for path in original_png_paths
                ]
                for path, item in uploaded_original:
                    url = item.get("url", "").strip()
                    if not url:
                        continue
                    image_map[path.name] = url
                    image_map[path.stem] = url

                uploaded_generated = [
                    (chart_name, path, client.upload_image_material(path))
                    for chart_name, path in generated_chart_paths.items()
                ]
                for chart_name, path, item in uploaded_generated:
                    url = item.get("url", "").strip()
                    if not url:
                        continue
                    image_map[chart_name] = url
                    image_map[path.name] = url
                    image_map[path.stem] = url

                if journal_cover_path.exists():
                    cover_upload = client.upload_image_material(journal_cover_path)
                    journal_thumb_media_id = cover_upload.get("media_id", "").strip()
                    if not journal_thumb_media_id:
                        raise RuntimeError(f"cover.png uploaded but no media_id returned: {journal_cover_path}")
                elif not journal_thumb_media_id and len(uploaded_original) > 4:
                    journal_thumb_media_id = uploaded_original[4][1].get("media_id", "")

            journal_article = build_journal_article(
                markdown_items=md_texts,
                image_map=image_map,
                author=config.draft_author,
                thumb_media_id=journal_thumb_media_id,
                brand_logo_url=brand_logo_url,
            )
            articles = [journal_article] + articles
            journal_diag = {
                "md_count": len(md_files),
                "png_count": len(png_files),
                "cover_present": journal_cover_path.exists(),
                "chart_config_present": chart_config_path.exists(),
                "generated_chart_count": len(generated_chart_paths),
                "xhs_chart_dir": str(journal_day_dir / "xhs"),
                "image_map_count": len(image_map),
                "brand_logo_url_set": bool(brand_logo_url),
                "thumb_media_id_source": (
                    "cover.png"
                    if journal_cover_path.exists()
                    else ("config/default" if journal_thumb_media_id else "none")
                ),
            }
            diagnostics["modules"]["journal"] = {"status": "success", **journal_diag}
            diagnostics["journal"] = journal_diag
            journal_success = True
        except Exception as exc:
            diagnostics["modules"]["journal"] = {"status": "failed", "error": str(exc)}
            LOGGER.exception("期刊模块执行失败")

    if not arxiv_success and not journal_success:
        diagnostics["steps"]["draft_publish"] = {"status": "skipped", "reason": "no_articles"}
        diagnostics["steps"]["ai_enhance"] = {"status": "skipped", "reason": "no_arxiv_output"}
        diagnostics["steps"]["git_sync"] = {"status": "skipped", "reason": "no_module_succeeded"}
        _raise_with_diagnostics("both modules failed", diagnostics)

    if len(articles) > 8:
        articles = articles[:8]

    title_max_bytes = int(os.environ.get("WECHAT_TITLE_MAX_BYTES", "0"))
    original_titles = [article.title for article in articles]
    if title_max_bytes > 0:
        _set_article_titles(
            articles,
            [_truncate_wechat_title(title, max_bytes=title_max_bytes) for title in original_titles],
        )

    draft_media_id = None
    if dry_run:
        diagnostics["steps"]["draft_publish"] = {"status": "skipped", "reason": "dry_run"}
    elif not articles:
        diagnostics["steps"]["draft_publish"] = {"status": "skipped", "reason": "no_articles"}
    else:
        try:
            client = WechatClient(config.wechat_app_id, config.wechat_app_secret)
            draft_resp = client.add_draft([a.to_dict() for a in articles])
            draft_media_id = draft_resp.get("media_id")
            diagnostics["steps"]["draft_publish"] = {
                "status": "success",
                "media_id": draft_media_id,
                "articles_count": len(articles),
            }
        except WechatAPIError as exc:
            if exc.errcode == 45003:
                draft_resp = _retry_add_draft_with_safe_titles(
                    client=client,
                    articles=articles,
                    base_titles=original_titles,
                    configured_limit=title_max_bytes,
                )
                draft_media_id = draft_resp.get("media_id")
                diagnostics["steps"]["draft_publish"] = {
                    "status": "success",
                    "media_id": draft_media_id,
                    "articles_count": len(articles),
                    "title_retry": True,
                    "final_title_bytes": [len(article.title.encode("utf-8")) for article in articles],
                }
            else:
                diagnostics["steps"]["draft_publish"] = {"status": "failed", "error": str(exc)}
                _raise_with_diagnostics(f"draft publish failed: {exc}", diagnostics)
        except Exception as exc:
            diagnostics["steps"]["draft_publish"] = {"status": "failed", "error": str(exc)}
            _raise_with_diagnostics(f"draft publish failed: {exc}", diagnostics)

    if arxiv_success:
        try:
            ai_ok = ai_enhance_only(date_set=config.date_str)
            if not ai_ok:
                raise RuntimeError("ai_enhance_only returned False")
            diagnostics["steps"]["ai_enhance"] = {"status": "success"}
        except Exception as exc:
            diagnostics["steps"]["ai_enhance"] = {"status": "failed", "error": str(exc)}
            _raise_with_diagnostics(f"ai enhance failed: {exc}", diagnostics)
    else:
        reason = "arxiv_module_disabled" if not run_arxiv_module else "arxiv_module_failed"
        diagnostics["steps"]["ai_enhance"] = {"status": "skipped", "reason": reason}

    try:
        git_sync_result = run_git_sync_internal(today_str=config.date_str)
        diagnostics["git_sync"] = git_sync_result
        if git_sync_result.get("status") == "success":
            diagnostics["steps"]["git_sync"] = {"status": "success", **git_sync_result}
        else:
            diagnostics["steps"]["git_sync"] = {"status": "failed", **git_sync_result}
    except Exception as exc:
        diagnostics["git_sync"] = {"status": "error", "message": str(exc)}
        diagnostics["steps"]["git_sync"] = {"status": "failed", "error": str(exc)}
        LOGGER.exception("git同步执行失败")

    if journal_success:
        try:
            xhs_model_name = os.environ.get("XHS_MODEL_NAME", "qwen/Qwen3-14B-FP8")
            xhs_result = generate_xiaohongshu_copy_from_journal(
                journal_markdown_for_xhs,
                model_name=xhs_model_name,
            )
            xhs_content = str(xhs_result.get("content", ""))
            diagnostics["steps"]["xiaohongshu_copy"] = {
                "status": "success",
                "provider": xhs_result.get("provider"),
                "model_name": xhs_result.get("model_name"),
                "lease_id": xhs_result.get("lease_id"),
                "content_preview": xhs_content[:200],
            }
            diagnostics["xiaohongshu_copy"] = xhs_result
        except Exception as exc:
            diagnostics["steps"]["xiaohongshu_copy"] = {"status": "failed", "error": str(exc)}
            diagnostics["xiaohongshu_copy"] = {"status": "failed", "error": str(exc)}
            LOGGER.exception("小红书文案生成失败")
    else:
        reason = "journal_module_disabled" if not run_journal_module else "journal_module_failed"
        diagnostics["steps"]["xiaohongshu_copy"] = {"status": "skipped", "reason": reason}

    enabled_modules_count = int(run_arxiv_module) + int(run_journal_module)
    succeeded_modules_count = int(arxiv_success) + int(journal_success)
    result_status = "success" if succeeded_modules_count == enabled_modules_count else "partial_success"

    return PublishResult(
        status=result_status,
        date=config.date_str,
        articles_count=len(articles),
        article_titles=[a.title for a in articles],
        draft_media_id=draft_media_id,
        diagnostics=diagnostics,
    )
