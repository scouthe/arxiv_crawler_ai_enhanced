import re
from datetime import datetime

from .constants import (
    ARTICLE_TEMPLATE,
    BOTTOM_FOOTER,
    CATEGORY_HEADER_TEMPLATE,
    DIGEST_TEMPLATE,
    GROUP_DEFINITIONS,
    IMAGE_HTML,
    LINK_SECTION,
    MAX_PAPERS_PER_CATEGORY,
    PROFILE_HTML,
    TOP_HEADER,
)
from .models import DraftArticle, PaperCardData


def _split_blocks_by_h2(text: str) -> list[str]:
    return [s for s in re.split(r"(?=^##\s)", text, flags=re.M) if s.strip()]


def filter_categories(markdown_text: str, group_def: dict) -> tuple[str, dict[str, int]]:
    stats = {key: 0 for key in group_def["stats_keys"]}
    filtered_blocks: list[str] = []
    for block in _split_blocks_by_h2(markdown_text):
        m = re.search(r"^##\s*(.+)$", block, flags=re.M)
        if not m:
            continue
        current_title = m.group(1).strip()
        header_line = m.group(0)
        if not any(keyword in current_title for keyword in group_def["keywords"]):
            continue
        body = block[m.end() :].strip()
        papers = [s for s in re.split(r"(?=【\d+】)", body) if s.strip()]
        for title_marker, stat_key in group_def["stats_by_title_contains"]:
            if title_marker in current_title:
                stats[stat_key] = len(papers)
                break
        limited = papers[:MAX_PAPERS_PER_CATEGORY]
        filtered_blocks.append(header_line + "\n\n" + "".join(limited))
    return "\n\n".join(filtered_blocks), stats


def split_papers(filtered_text: str, stats: dict[str, int]) -> list[PaperCardData]:
    cards: list[PaperCardData] = []
    for block in _split_blocks_by_h2(filtered_text):
        block = block.strip()
        m = re.search(r"^##\s*(.+)$", block, flags=re.M)
        category_title = "Daily Papers"
        category_html = ""
        if m:
            category_title = m.group(1).strip()
            category_html = CATEGORY_HEADER_TEMPLATE.replace("{{CATEGORY_TITLE}}", category_title)
            block = block.replace(m.group(0), "", 1).strip()

        first_paper_index = re.search(r"【\d+】", block)
        if first_paper_index:
            block = block[first_paper_index.start() :]

        papers = [s for s in re.split(r"(?=【\d+】)", block) if s.strip()]
        first = True
        for paper in papers:
            card = PaperCardData(stats=stats.copy())
            for line in paper.splitlines():
                line = line.strip()
                if line.startswith("【"):
                    card.english_title = line
                elif line.startswith("- **标题**:"):
                    card.chinese_title = line.split(":", 1)[1].strip()
                elif line.startswith("- **链接**:"):
                    card.arxiv_link = line.split(":", 1)[1].strip()
                elif line.startswith("> **作者**:"):
                    card.authors = line.split(":", 1)[1].strip()
                elif line.startswith("> **摘要**:"):
                    card.chinese_abstract = line.split(":", 1)[1].strip()
                elif line.startswith("> **Abstract**:"):
                    card.english_abstract = line.split(":", 1)[1].strip()
            card.category_html = category_html if first else ""
            cards.append(card)
            first = False
    return cards


def build_html_output(cards: list[PaperCardData], summary_text: str) -> str:
    html_list: list[str] = []
    for card in cards:
        rendered = ARTICLE_TEMPLATE
        rendered = rendered.replace("{{ENGLISH_TITLE}}", card.english_title or "")
        rendered = rendered.replace("{{CHINESE_TITLE}}", card.chinese_title or "")
        rendered = rendered.replace("{{ARXIV_LINK}}", card.arxiv_link or "")
        rendered = rendered.replace("{{AUTHORS}}", card.authors or "")
        rendered = rendered.replace("{{CHINESE_ABSTRACT}}", card.chinese_abstract or "")
        rendered = rendered.replace("{{ENGLISH_ABSTRACT}}", card.english_abstract or "")
        html_list.append(card.category_html + rendered.strip())

    summary_header = (
        '<p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p><section style=" text-align: left;'
        ' line-height: 1.75; font-family: -apple-system-font,BlinkMacSystemFont, Helvetica Neue, PingFang SC, '
        'Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei ,Arial,sans-serif; font-size: 16px">'
        f'<h2 id="0" style=" text-align: center; line-height: 1.75; font-family: -apple-system-font,'
        'BlinkMacSystemFont, Helvetica Neue, PingFang SC, Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei '
        ',Arial,sans-serif; font-size: 19.2px; display: table; padding: 0 0.2em; margin: 4em auto 1em; color: #fff; '
        'background: #0F4C81; font-weight: bold;margin-top: 0" data-heading="true">'
        f"{summary_text}</h2></section>"
    )
    merged_body = "<br/>".join(html_list)
    return TOP_HEADER + summary_header + PROFILE_HTML + LINK_SECTION + merged_body + IMAGE_HTML + BOTTOM_FOOTER


def build_three_arxiv_articles(
    markdown_text: str,
    date_str: str,
    author: str,
    source_url: str,
    thumb_main: str,
    thumb_audio: str,
    thumb_hcro: str,
) -> tuple[list[DraftArticle], dict]:
    thumb_map = {"main": thumb_main, "audio": thumb_audio, "hcro": thumb_hcro}
    diagnostics = {}
    articles: list[DraftArticle] = []

    for group in GROUP_DEFINITIONS:
        filtered_text, stats = filter_categories(markdown_text, group)
        cards = split_papers(filtered_text, stats)
        summary_text = group["summary_tpl"].format(**stats)
        html_content = build_html_output(cards, summary_text)

        title = group["article_title_tpl"].format(date=date_str)
        digest = DIGEST_TEMPLATE.format(date=date_str)
        article = DraftArticle(
            title=title,
            author=author,
            digest=digest,
            show_cover_pic=1,
            content=html_content,
            content_source_url=source_url,
            thumb_media_id=thumb_map[group["group_id"]],
            need_open_comment=1,
        )
        articles.append(article)
        diagnostics[f"group_{group['group_id']}"] = {
            "stats": stats,
            "cards_after_filter": len(cards),
            "filtered_text_len": len(filtered_text),
        }
    return articles, diagnostics


def today_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

