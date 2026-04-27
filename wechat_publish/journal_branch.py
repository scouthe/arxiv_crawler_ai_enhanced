import os
import re
from pathlib import Path

from .constants import IMAGE_HTML
from .journal_format import md_to_xuanji_html
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
SLOGAN_HTML = (
    f'<p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p>'
    f'<section style="text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; font-size: 16px">'
    f'<h1 style="text-align: center; line-height: 1.75; font-family: {FONT_STYLE}; '
    f'font-size: 19.2px; display: table; padding: 0 1em; border-bottom: 2px solid {H1_COLOR}; '
    f'margin: 2em auto 1em; color: #3f3f3f; font-weight: bold; margin-top: 0" data-heading="true">'
    f'<strong style="text-align: left; line-height: 1.75; font-family: {FONT_STYLE}; '
    f'font-size: inherit; color: {H1_COLOR}; font-weight: bold">璇玑枢，助力学术成长，点亮科研之路</strong>'
    f"</h1></section>"
)
INTRO_HTML = SLOGAN_HTML + PROFILE_HTML + HEJI_HTML
DEFAULT_BRAND_LOGO_PATH = Path(
    os.environ.get(
        "WECHAT_BRAND_LOGO_PATH",
        "/home/heheheh/Documents/coding/gongzhonghao/logo/璇玑枢_横版透明底.png",
    )
)


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
    return md_files, png_files


def _clean_image_alt(alt_text: str) -> str:
    alt = alt_text.strip()
    if alt.lower() in {"alt text", "alt", "image", "figure"}:
        return ""
    return alt


def _resolve_image_url(alt_text: str, source: str, image_map: dict[str, str]) -> str:
    candidates: list[str] = []
    alt = _clean_image_alt(alt_text)
    source = source.strip()

    if alt:
        candidates.append(alt)
    if source:
        candidates.append(source)
        source_name = Path(source).name
        if source_name and source_name not in candidates:
            candidates.append(source_name)
        source_stem = Path(source_name).stem
        if source_stem and source_stem not in candidates:
            candidates.append(source_stem)

    for key in candidates:
        value = image_map.get(key, "").strip()
        if value:
            return value
    return ""


def replace_markdown_images(markdown_text: str, image_map: dict[str, str] | list[str] | None) -> str:
    text = re.sub(r"^(#+)\s*\*\*(.*?)\*\*\s*$", r"\1 \2", markdown_text, flags=re.M)
    if image_map is None:
        image_map = {}

    if isinstance(image_map, list):
        idx = 0

        def _replace_sequential(_m):
            nonlocal idx
            if idx < len(image_map):
                url = image_map[idx]
                idx += 1
                return f"![]({url})"
            return ""

        return re.sub(r"!\[[^\]]*\]\([^\)]*\)", _replace_sequential, text)

    def _replace_named(match: re.Match[str]) -> str:
        alt_text = match.group("alt")
        source = match.group("src")
        url = _resolve_image_url(alt_text, source, image_map)
        if not url:
            return ""
        clean_alt = _clean_image_alt(alt_text)
        return f"![{clean_alt}]({url})" if clean_alt else f"![]({url})"

    return re.sub(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^\)]*)\)", _replace_named, text)


def extract_markdown_title(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def markdown_to_wechat_html(raw_content: str, brand_logo_url: str = "") -> tuple[str, str]:
    markdown_text = raw_content.replace("\r\n", "\n")
    markdown_text = re.sub(r"^\s*璇玑枢，助力学术成长，点亮科研之路\s*$", "", markdown_text, flags=re.M)
    markdown_text = markdown_text.strip()
    real_title = extract_markdown_title(markdown_text)
    body_html = md_to_xuanji_html(markdown_text, brand_logo_url=brand_logo_url)
    section = body_html + '<p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p>'
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
    image_map: dict[str, str] | list[str] | None,
    author: str,
    thumb_media_id: str,
    brand_logo_url: str = "",
) -> DraftArticle:
    replaced = [replace_markdown_images(md, image_map) for md in markdown_items]
    converted = [markdown_to_wechat_html(md, brand_logo_url=brand_logo_url) for md in replaced]
    html_outputs = post_process_journal_html([x[0] for x in converted])
    titles = [x[1] for x in converted]
    content = html_outputs[0] if html_outputs else ""
    title = titles[0] if titles else "璇玑枢学术专递"

    return DraftArticle(
        title=title,
        author=author,
        digest="助力学术成长，点亮科研之路",
        show_cover_pic=1,
        content=content,
        thumb_media_id=thumb_media_id,
        need_open_comment=1,
    )
