import re
from pathlib import Path

from .constants import IMAGE_HTML
from .models import DraftArticle

FONT_STYLE = "-apple-system-font,BlinkMacSystemFont, Helvetica Neue, PingFang SC, Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei ,Arial,sans-serif"
H1_COLOR = "#0F4C81"
DEFAULT_P_STYLE = (
    f"text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; font-size: 16px; "
    "margin: 1.5em 8px; letter-spacing: 0.1em; color: #3f3f3f"
)
PROFILE_HTML = """<section class="mp_profile_iframe_wrp" nodeleaf="">
  <mp-common-profile class="js_uneditable custom_select_card mp_profile_iframe"
    data-pluginname="mpprofile"
    data-nickname="璇玑枢"
    data-alias="mizhiNo1"
    data-from="0"
    data-headimg="http://mmbiz.qpic.cn/mmbiz_png/pdoYWlyPiaWFPmEWuRgRQVk08RkmAVKAxKSLHkiakfKDSScOp0iaH99L3NRvcicuVK6mtTibD9GNiaG5fFFCx956PZOA/0?wx_fmt=png"
    data-signature="最干货、暖心、有用的研究生学习类公众号，提供求学期间的经验分享、学习资源、生活分享，旨在帮助读研学生解疑答惑和真正提升自我！"
    data-id="MzU5MTU5NTI3MQ=="
    data-is_biz_ban="0"
    data-service_type="1"
    data-verify_status="0">
  </mp-common-profile>
</section>
<section><span leaf=""><br></span></section>"""
HEJI_HTML = '<section style="background:#f3f3f3;padding:18px 20px 14px 20px;margin:16px 0;"><span leaf=""><a class="normal_text_link" target="_blank" style="font-size: 20px;line-height: 1.6;color: rgb(17, 17, 17);font-weight: 600;text-decoration: none;display: inline-block;" href="https://mp.weixin.qq.com/s?__biz=MzU5MTU5NTI3MQ==&amp;mid=2247486131&amp;idx=1&amp;sn=68a45957b64be87716f4275a3491ee4d&amp;scene=21#wechat_redirect" textvalue="科研期刊分类合集（持续更新）" data-itemshowtype="0" linktype="text" data-linktype="2">科研期刊分类合集（持续更新）</a></span><section style="width:72px;height:3px;background:#2b6ff2;margin:10px 0 12px 0;"><span leaf=""><br></span></section><section style="font-size:14px;line-height:1.8;color:#9aa0a6;"><span leaf="">合集对已介绍的多本科研期刊按研究方向与期刊定位进行汇总与分类。</span></section></section>'


def load_journal_assets(base_dir: Path, date_str: str) -> tuple[list[Path], list[Path]]:
    day_dir = base_dir / date_str
    md_files = sorted(day_dir.glob("*.md"))
    png_files = sorted(day_dir.glob("*.png"))
    return md_files, png_files


def replace_markdown_images(markdown_text: str, image_urls: list[str]) -> str:
    text = re.sub(r"^(#+)\s*\*\*(.*?)\*\*\s*$", r"\1 \2", markdown_text, flags=re.M)
    idx = 0

    def _replace(_m):
        nonlocal idx
        if idx < len(image_urls):
            url = image_urls[idx]
            idx += 1
            return f"![]({url})"
        return ""

    return re.sub(r"!\[[^\]]*\]\([^\)]*\)", _replace, text)


def markdown_to_wechat_html(raw_content: str) -> tuple[str, str]:
    markdown_text = raw_content.replace("\r\n", "\n")
    markdown_text = re.sub(r"^\s*璇玑枢，助力学术成长，点亮科研之路\s*$", "", markdown_text, flags=re.M)
    real_title = ""
    heading_id = 0

    def h1_replace(match):
        nonlocal real_title, heading_id
        content = match.group(1).strip()
        if not real_title:
            real_title = content
            slogan_text = "璇玑枢，助力学术成长，点亮科研之路"
            h1 = (
                f'<h1 id="{heading_id}" style="text-align: center; line-height: 1.75; font-family: {FONT_STYLE};'
                f' font-size: 19.2px; display: table; padding: 0 1em; border-bottom: 2px solid {H1_COLOR}; '
                'margin: 2em auto 1em; color: #3f3f3f; font-weight: bold;margin-top: 0" data-heading="true">'
                f'<strong style="text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; '
                f'font-size: inherit; color: {H1_COLOR}; font-weight: bold">{slogan_text}</strong></h1>'
            )
            heading_id += 1
            return h1 + PROFILE_HTML + HEJI_HTML
        h1 = (
            f'<h1 id="{heading_id}" style="text-align: center; line-height: 1.75; font-family: {FONT_STYLE};'
            f' font-size: 19.2px; display: table; padding: 0 1em; border-bottom: 2px solid {H1_COLOR}; '
            'margin: 2em auto 1em; color: #3f3f3f; font-weight: bold;margin-top: 0" data-heading="true">'
            f'<strong style="text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; '
            f'font-size: inherit; color: {H1_COLOR}; font-weight: bold">{content}</strong></h1>'
        )
        heading_id += 1
        return h1

    markdown_text = re.sub(r"^#\s(.*?)$", h1_replace, markdown_text, flags=re.M)

    def h2_replace(match):
        nonlocal heading_id
        content = match.group(1)
        h = (
            f'<h2 id="{heading_id}" style="text-align: center; line-height: 1.75; font-family: {FONT_STYLE}; '
            f'font-size: 19.2px; display: table; padding: 0 0.2em; margin: 4em auto 2em; color: #fff; '
            f'background: {H1_COLOR}; font-weight: bold" data-heading="true">{content}</h2>'
        )
        heading_id += 1
        return h

    markdown_text = re.sub(r"^##\s(.*?)$", h2_replace, markdown_text, flags=re.M)

    def h3_replace(match):
        nonlocal heading_id
        content = match.group(1)
        h = (
            f'<h3 id="{heading_id}" style="text-align: left; line-height: 1.2; font-family: {FONT_STYLE}; '
            f'font-size: 17.6px; padding-left: 8px; border-left: 3px solid {H1_COLOR}; margin: 2em 8px 0.75em 0; '
            f'color: #3f3f3f; font-weight: bold" data-heading="true">{content}</h3>'
        )
        heading_id += 1
        return h

    markdown_text = re.sub(r"^###\s(.*?)$", h3_replace, markdown_text, flags=re.M)

    markdown_text = re.sub(
        r"!\[(.*?)\]\((.*?)\)",
        lambda m: (
            f'<figure style="text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; '
            'font-size: 16px; margin: 1.5em 8px; color: #3f3f3f">'
            f'<img alt="{m.group(1)}" title="null" src="{m.group(2)}" style="text-align: left; line-height: 1.75;'
            f' font-family: {FONT_STYLE}; font-size: 16px; display: block; max-width: 100%; margin: 0.1em auto 0.5em;'
            ' border-radius: 4px">'
            f'<figcaption style="text-align: center; line-height: 1.75; font-family: {FONT_STYLE}; '
            f'font-size: 0.8em; color: #888">{m.group(1)}</figcaption></figure>'
        ),
        markdown_text,
    )

    markdown_text = re.sub(
        r"(\n(\s*[\*-]\s.*))+",
        lambda m: _unordered_list_to_html(m.group(0)),
        markdown_text,
    )
    markdown_text = re.sub(r"(\n(\s*\d+\.\s.*))+", lambda m: _ordered_list_to_html(m.group(0)), markdown_text)
    markdown_text = re.sub(
        r"\*\*(.*?)\*\*",
        lambda m: (
            f'<strong style="text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; font-size: inherit; '
            f'color: {H1_COLOR}; font-weight: bold">{m.group(1)}</strong>'
        ),
        markdown_text,
    )
    markdown_text = re.sub(r"\[(.*?)\]\((.*?)\)", lambda m: m.group(2), markdown_text)
    markdown_text = re.sub(r"<(http|https):\/\/.*?>", lambda m: m.group(0).strip("<>"), markdown_text)

    markdown_text = re.sub(r"\n{2,}", "BLOCK_SEP", markdown_text)
    markdown_text = markdown_text.replace("\n", "")
    markdown_text = markdown_text.replace("BLOCK_SEP", "\n\n")

    parts = [p.strip() for p in re.split(r"\n{2,}", markdown_text) if p.strip()]
    final_html = "".join(
        p if p.startswith("<h") or p.startswith("<ul") or p.startswith("<ol") or p.startswith("<figure") else f'<p style="{DEFAULT_P_STYLE}">{p}</p>'
        for p in parts
    )
    section = (
        f'<p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p><section style=" text-align: left; '
        f'line-height: 1.75; font-family: {FONT_STYLE}; font-size: 16px">{final_html}</section>'
        '<p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p>'
    )
    return section, (real_title or "璇玑枢学术专递")


def _unordered_list_to_html(block: str) -> str:
    lines = [x for x in block.strip().split("\n") if x.strip().startswith(("*", "-"))]
    if not lines:
        return block
    li_style = (
        f"text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; font-size: 16px; text-indent: -1em; "
        "display: block; margin: 0.2em 8px; color: #3f3f3f"
    )
    ul_style = (
        f"text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; font-size: 16px; list-style: circle; "
        "padding-left: 1em; margin-left: 0; color: #3f3f3f"
    )
    items = "".join(f'<li style="{li_style}">• {re.sub(r"^\s*[\*-]\s", "", x).strip()}</li>' for x in lines)
    return f'<ul style="{ul_style}">{items}</ul>'


def _ordered_list_to_html(block: str) -> str:
    lines = [x for x in block.strip().split("\n") if re.match(r"^\s*\d+\.\s", x)]
    if not lines:
        return block
    li_style = (
        f"text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; font-size: 16px; text-indent: -1em; "
        "display: block; margin: 0.2em 8px; color: #3f3f3f"
    )
    ol_style = (
        f"text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; font-size: 16px; padding-left: 1em; "
        "margin-left: 0; color: #3f3f3f"
    )
    rendered = []
    for line in lines:
        num = re.match(r"^\s*(\d+)\.\s", line)
        number = num.group(1) if num else ""
        content = re.sub(r"^\s*\d+\.\s", "", line).strip()
        rendered.append(f'<li style="{li_style}">{number}. {content}</li>')
    return f'<ol style="{ol_style}">{"".join(rendered)}</ol>'


def post_process_journal_html(html_outputs: list[str]) -> list[str]:
    processed = []
    for html_content in html_outputs:
        html_content = html_content.rstrip()
        if html_content.endswith('"'):
            html_content = html_content[:-1]
        for target_text in ["期刊官网", "期刊投稿网址"]:
            pattern = re.compile(
                rf'(<p style="[^>]*?)(\s*font-size:\s*[^;"]+;?\s*)([^>]*?>)([^<]*?{re.escape(target_text)}.*?)(</p>)',
                flags=re.S,
            )
            html_content = pattern.sub(
                lambda m: m.group(1) + re.sub(r"font-size:\s*[^;\"]+", "font-size: 14px", m.group(2)) + m.group(3) + m.group(4) + m.group(5),
                html_content,
            )
        html_content = html_content.replace(
            "**璇玑枢，我以渺小，与你同行——相信您也能在这片学术星空下留下自己的光彩。",
            "璇玑枢，我以渺小，与你同行——相信您也能在这片学术星空下留下自己的光彩。",
        )
        html_content += IMAGE_HTML
        processed.append(html_content)
    return processed


def build_journal_article(
    markdown_items: list[str],
    image_urls: list[str],
    author: str,
    thumb_media_id: str,
) -> DraftArticle:
    replaced = [replace_markdown_images(md, image_urls) for md in markdown_items]
    converted = [markdown_to_wechat_html(md) for md in replaced]
    html_outputs = post_process_journal_html([x[0] for x in converted])
    titles = [x[1] for x in converted]
    content = html_outputs[0] if html_outputs else ""
    title = titles[0] if titles else "璇玑枢学术专递"
    if len(title) > 60:
        title = title[:60] + "..."

    return DraftArticle(
        title=title,
        author=author,
        digest="助力学术成长，点亮科研之路",
        show_cover_pic=1,
        content=content,
        thumb_media_id=thumb_media_id,
        need_open_comment=1,
    )

