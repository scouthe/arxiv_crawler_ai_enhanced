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
    data-from="0"
    data-headimg="http://mmbiz.qpic.cn/sz_mmbiz_png/Bps2mXQvSQiaFnHeBCs7xpwn7nA5icgHYLcsrWEbajjxSLMRBhIhhFqj8m9VSAP0vkAcnS2O3PbKUic5H1M2xKpDicyUic7d2iaqvJiaVDZWiacaLfQ/0?wx_fmt=png"
    data-signature="期刊介绍，论文润色，深度学习，人工智能"
    data-id="MzY4OTE0NjQwMA=="
    data-is_biz_ban="0"
    data-service_type="1"
    data-verify_status="2">
  </mp-common-profile>
</section>
<section>
  <span leaf=""><br></span>
</section>
<p style="display: none;">
  <mp-style-type data-value="3">
  </mp-style-type>
</p>"""
HEJI_HTML = """<section style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);margin: 16px 0px;padding: 18px 20px 14px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;color: rgba(0, 0, 0, 0.9);font-family: -apple-system-font, BlinkMacSystemFont, &quot;Helvetica Neue&quot;, &quot;PingFang SC&quot;, &quot;Hiragino Sans GB&quot;, &quot;Microsoft YaHei UI&quot;, &quot;Microsoft YaHei&quot;, Arial, sans-serif;font-size: 16px;font-style: normal;font-variant-ligatures: normal;font-variant-caps: normal;font-weight: 400;letter-spacing: 0.544px;orphans: 2;text-align: justify;text-indent: 0px;text-transform: none;widows: 2;word-spacing: 0px;-webkit-text-stroke-width: 0px;white-space: normal;text-decoration-thickness: initial;text-decoration-style: initial;text-decoration-color: initial;background: rgb(243, 243, 243);visibility: visible;" data-pm-slice="0 0 []">
  <span leaf="" style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;visibility: visible;"><a class="normal_text_link" target="_blank" style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);margin: 0px;padding: 0px;outline: 0px;color: rgb(17, 17, 17);text-decoration: none;-webkit-user-drag: none;cursor: default;max-width: 100%;font-size: 20px;line-height: 1.6;font-weight: 600;display: inline-block;visibility: visible;box-sizing: border-box !important;overflow-wrap: break-word !important;" href="https://mp.weixin.qq.com/s?__biz=MzY4OTE0NjQwMA==&amp;mid=2247485611&amp;idx=1&amp;sn=e1f0e99a075476bd4b9e4ad40a3adccf&amp;source=41&amp;poc_token=HLtbuWmjCxPZuZHXYo-qKhtwRiz7oN3d1HegSgJG&amp;scene=21#wechat_redirect" textvalue="科研期刊分类合集（持续更新）" data-itemshowtype="0" linktype="text" data-linktype="2">科研期刊分类合集（持续更新）</a></span>
  <section style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);margin: 10px 0px 12px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;width: 72px;height: 3px;background: rgb(43, 111, 242);text-align: justify;visibility: visible;">
    <span leaf="" style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;visibility: visible;"><br></span>
  </section>
  <section style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;font-size: 14px;line-height: 1.8;color: rgb(154, 160, 166);text-align: justify;visibility: visible;">
    <span leaf="" style="-webkit-tap-highlight-color: rgba(0, 0, 0, 0);margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;visibility: visible;">合集对已介绍的多本科研期刊按研究方向与期刊定位进行汇总与分类。</span>
  </section>
</section>
<p style="display: none;">
  <mp-style-type data-value="3">
  </mp-style-type>
</p>"""


def load_journal_assets(base_dir: Path, date_str: str) -> tuple[list[Path], list[Path]]:
    # Expected layout: <base_dir>/<YYYY>/<MM>/<YYYY-MM-DD>/
    year, month, _day = date_str.split("-")
    day_dir = base_dir / year / month / date_str
    if not day_dir.exists():
        raise FileNotFoundError(f"journal assets directory not found: {day_dir}")
    md_files = sorted(day_dir.glob("*.md"))
    png_files = sorted(day_dir.glob("*.png"))
    if not md_files:
        raise FileNotFoundError(f"journal markdown not found in: {day_dir}")
    if not png_files:
        raise FileNotFoundError(f"journal images not found in: {day_dir}")
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
