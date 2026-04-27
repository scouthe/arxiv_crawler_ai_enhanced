import html
import os
import re

# =========================
# 璇玑枢品牌视觉配置
# =========================
THEME_COLOR = "#1C2F6C"          # 主深蓝，不变
THEME_COLOR_LIGHT = "#9E8BF2"    # 稍亮一点的浅紫
THEME_COLOR_MID = "#4F6FE3"      # 更清晰一点的蓝紫
ALERT_COLOR = "#B53A32"          # 比原来更亮的绛红
TEXT_COLOR = "#222222"
SUB_TEXT_COLOR = "#667085"
LIGHT_BG = "#F7F8FC"
LINE_COLOR = "#D9DEEA"

BRAND_LOGO_URL = "/home/heheheh/Documents/coding/gongzhonghao/logo/璇玑枢_横版透明底.png"

# 强化两端对齐样式
JUSTIFY_STYLE = "text-align: justify; text-justify: inter-ideograph; word-break: break-word;"

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

# =========================
# 文本格式化
# =========================
def _format_inline(text: str) -> str:
    """
    行内格式：
    1. **普通重点** -> 深色加粗
    2. ==强重点== -> 更清晰的蓝紫高亮
    3. !!提醒!! -> 更亮一点的绛红提醒
    """
    text = re.sub(r'\\([*.~_=!\\-`#])', r'\1', text)
    escaped = html.escape(text.strip())

    # 1) 风险 / 强警示
    escaped = re.sub(
        r"!!(.*?)!!",
        rf'<strong style="color: {ALERT_COLOR}; font-weight: 700;">\1</strong>',
        escaped,
        flags=re.S,
    )

    # 2) 一眼看到的信息：更亮一点，但不过分
    escaped = re.sub(
        r"==(.*?)==",
        rf'<span style="display: inline; padding: 1px 6px; border-radius: 6px; '
        rf'background: linear-gradient(90deg, rgba(79,111,227,0.14) 0%, rgba(158,139,242,0.22) 100%); '
        rf'color: #2A3FA3; font-weight: 700;">\1</span>',
        escaped,
        flags=re.S,
    )

    # 3) 普通重点
    escaped = re.sub(
        r"\*\*(.*?)\*\*",
        r'<strong style="color: #111827; font-weight: 700;">\1</strong>',
        escaped,
        flags=re.S,
    )

    return escaped


def _parse_list_items(block: str, ordered: bool = False) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    marker_pattern = r"^\d+\.\s+" if ordered else r"^[\-\*•]\s+"

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(marker_pattern, stripped):
            if current:
                items.append(" ".join(current).strip())
            current = [re.sub(marker_pattern, "", stripped)]
        elif current:
            current.append(stripped)
        else:
            current = [stripped]

    if current:
        items.append(" ".join(current).strip())
    return items


# =========================
# 主转换函数
# =========================
def md_to_xuanji_html(md_text, brand_logo_url=None):
    html_parts = []
    # `None` means "use the configured default logo"; an empty string means
    # "explicitly disable the logo for this render".
    if brand_logo_url is None:
        resolved_logo_url = BRAND_LOGO_URL.strip()
    else:
        resolved_logo_url = brand_logo_url.strip()

    # 外层容器
    html_parts.append(f'''
<section style="
    box-sizing: border-box;
    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'PingFang SC',
                 'Hiragino Sans GB', 'Microsoft YaHei UI', 'Microsoft YaHei', Arial, sans-serif;
    font-size: 16px;
    color: {TEXT_COLOR};
    line-height: 1.75;
    letter-spacing: 0.3px;
    padding: 0 12px;
    background-color: #fff;
    {JUSTIFY_STYLE}
    overflow-wrap: anywhere;
">
''')

    # 顶部品牌区：去掉固定 slogan，只保留系列标识 + logo
    logo_html = ""
    if resolved_logo_url:
        logo_html = f'''
        <section style="margin: 0 0 10px 0; text-align: left;">
            <img src="{html.escape(resolved_logo_url, quote=True)}"
                 style="max-height: 68px; max-width: 320px; display: block;" />
        </section>
'''
    html_parts.append(f'''
    <section style="margin-bottom: 22px;">
        <p style="margin: 0 0 12px 0; font-size: 14px; color: {SUB_TEXT_COLOR}; line-height: 1.6;">
            <span style="
                background: linear-gradient(90deg, rgba(28,47,108,0.10) 0%, rgba(176,148,244,0.16) 100%);
                color: {THEME_COLOR};
                padding: 3px 10px;
                border-radius: 999px;
                font-weight: 700;
            ">璇玑枢</span>
            <span style="display: inline-block; width: 8px;">&#8203;</span>
            <span style="color: {SUB_TEXT_COLOR};">系列：期刊信息变化分析</span>
        </p>

        {logo_html}

        <p style="
            margin: 0;
            width: 108px;
            height: 3px;
            line-height: 3px;
            font-size: 0;
            background: linear-gradient(90deg, {THEME_COLOR} 0%, {THEME_COLOR_MID} 55%, rgba(176,148,244,0.30) 100%);
            border-radius: 3px;
        ">&nbsp;</p>
    </section>
''')

    html_parts.append(PROFILE_HTML)

    md_text = re.sub(r'\\([*.~_\-`#])', r'\1', md_text)
    blocks = re.split(r'\n\s*\n', md_text.strip())
    in_abstract = False

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # 如果导语结束，补闭合
        if in_abstract and (block.startswith('## ') or block.startswith('### ') or block.startswith('# ') or re.match(r'^\-{3,}$', block)):
            in_abstract = False
            if html_parts[-1].startswith('    <p style="margin-bottom: 10px;'):
                html_parts[-1] = html_parts[-1].replace('margin-bottom: 10px;', 'margin-bottom: 0;')
            html_parts.append('    </section>')

        # TAG
        if block.startswith('TAG:'):
            continue

        # 一级标题
        elif block.startswith('# '):
            title = _format_inline(block[2:].strip())
            html_parts.append(f'''
    <h1 style="font-size: 24px; color: #111827; text-align: left; line-height: 1.42; margin: 0 0 10px 0; font-weight: 900;">
        {title}
    </h1>
    <p style="
        margin: 0 0 24px 0;
        width: 96px;
        height: 4px;
        line-height: 4px;
        font-size: 0;
        background: linear-gradient(90deg, {THEME_COLOR} 0%, {THEME_COLOR_MID} 55%, rgba(176,148,244,0.35) 100%);
        border-radius: 3px;
    ">&nbsp;</p>''')

        # 导语 / 导读
        elif block.startswith('## 导语') or block.startswith('## 导读'):
            in_abstract = True
            html_parts.append(f'''
    <section style="
        background: linear-gradient(180deg, #FAFBFF 0%, {LIGHT_BG} 100%);
        border: 1px solid #E5EAF4;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 24px;
        box-shadow: 0 0 0 1px rgba(28,47,108,0.02) inset;
        {JUSTIFY_STYLE}
    ">''')
            content = re.sub(r'^## 导[语读]\s*', '', block)
            if content:
                html_parts.append(f'    <p style="margin-bottom: 10px; color: #333; {JUSTIFY_STYLE}">{_format_inline(content).replace(chr(10), "<br/>")}</p>')
            continue

        elif in_abstract:
            html_parts.append(f'    <p style="margin-bottom: 10px; color: #333; {JUSTIFY_STYLE}">{_format_inline(block).replace(chr(10), "<br/>")}</p>')
            continue

        # 二级标题：微信友好的“伪斜角”品牌条
        elif block.startswith('## '):
            title = _format_inline(block[3:].strip())
            html_parts.append(f'''
        <section style="margin: 30px 0 14px 0; border-bottom: 1px solid rgba(28,47,108,0.18);">
            <p style="margin: 0; line-height: 1.5; font-size: 0;">
                <span style="
                    display: inline-block;
                    vertical-align: middle;
                    background: linear-gradient(90deg, {THEME_COLOR} 0%, {THEME_COLOR_MID} 55%, {THEME_COLOR_LIGHT} 100%);
                    color: #fff;
                    padding: 5px 12px 5px 12px;
                    border-radius: 3px 0 0 0;
                    font-size: 16px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                    line-height: 1.5;
                ">{title}</span><span style="
                    display: inline-block;
                    vertical-align: middle;
                    width: 0;
                    height: 0;
                    border-top: 17px solid transparent;
                    border-bottom: 17px solid transparent;
                    border-left: 14px solid {THEME_COLOR_LIGHT};
                    font-size: 0;
                    line-height: 0;
                ">&nbsp;</span>
            </p>
        </section>''')

        # 三级标题：导航节点感
        # v2.1：微信友好结构，左侧竖线改成 border-left，避免空 span 被清洗
        elif block.startswith('### '):
            title = _format_inline(block[4:].strip())
            html_parts.append(f'''
    <section style="margin: 22px 0 12px 0;">
        <p style="margin: 0; line-height: 1.45;">
            <span style="
                display: inline-block;
                border-left: 6px solid {THEME_COLOR};
                padding-left: 10px;
                color: {THEME_COLOR};
                font-size: 17px;
                font-weight: 700;
                line-height: 1.45;
            ">{title}</span>
        </p>
    </section>''')

        # 无序列表
        elif re.match(r'^[\-\*•]\s+', block):
            items = _parse_list_items(block, ordered=False)
            html_parts.append(f'''
    <section style="
        margin-bottom: 20px;
        color: #333;
        background: {LIGHT_BG};
        border: 1px solid #E3E8F2;
        padding: 14px 16px;
        border-radius: 10px;
        {JUSTIFY_STYLE}
    ">''')
            for item in items:
                rendered = _format_inline(item)
                html_parts.append(
                    f'''        <p style="margin: 0 0 8px 0; padding-left: 1.3em; text-indent: -1.3em; {JUSTIFY_STYLE}">
            <span style="color: {THEME_COLOR}; font-weight: 700;">• </span>{rendered}</p>'''
                )
            html_parts.append('    </section>')

        # 有序列表
        elif re.match(r'^\d+\.\s+', block):
            items = _parse_list_items(block, ordered=True)
            html_parts.append(f'''
    <section style="
        margin-bottom: 20px;
        color: #333;
        background: {LIGHT_BG};
        border: 1px solid #E3E8F2;
        padding: 14px 16px;
        border-radius: 10px;
        {JUSTIFY_STYLE}
    ">''')
            for idx, item in enumerate(items, 1):
                rendered = _format_inline(item)
                html_parts.append(
                    f'''        <p style="margin: 0 0 8px 0; padding-left: 1.9em; text-indent: -1.9em; {JUSTIFY_STYLE}">
            <span style="color: {THEME_COLOR}; font-weight: 700;">{idx}. </span>{rendered}</p>'''
                )
            html_parts.append('    </section>')

        # 分隔线
        # v2.1：微信友好结构，使用 hr，避免 flex / transform / 空装饰节点被清洗
        elif re.match(r'^\-{3,}$', block):
            html_parts.append(f'''
    <hr style="border: none; border-top: 1px solid #E8ECF3; margin: 34px 0 26px 0;">
''')

        # 图片
        elif block.startswith('![') and '](' in block:
            match = re.match(r'!\[(.*?)\]\((.*?)\)', block)
            if match:
                caption = _format_inline(match.group(1))
                url = html.escape(match.group(2).strip(), quote=True)
                if url.lower() in ['placeholder', '图', '']:
                    html_parts.append(
                        f'''<section style="
                            background: linear-gradient(180deg, #FBFCFF 0%, {LIGHT_BG} 100%);
                            color: {THEME_COLOR};
                            margin: 16px 0 10px 0;
                            padding: 52px 12px;
                            font-size: 14px;
                            border: 1px dashed #B7C3DA;
                            border-radius: 10px;
                            text-align: center;
                        ">
                            <p style="margin: 0; line-height: 1.6;">【此处点击替换图：{caption}】</p>
                        </section>'''
                    )
                else:
                    html_parts.append(
                        f'''<section style="margin: 16px 0 10px 0; text-align: center;">
                            <img src="{url}" style="max-width: 100%; border-radius: 8px; display: block; border: 1px solid #EDF1F7;" />
                        </section>'''
                    )
                html_parts.append(
                    f'''<p style="font-size: 13px; color: {SUB_TEXT_COLOR}; text-align: center; margin-bottom: 20px;">{caption}</p>'''
                )

        # 页脚
        elif block.startswith('FOOTER:'):
            lines = block[7:].strip().split('\n')
            html_parts.append(f'    <hr style="border: none; border-top: 1px solid #E8ECF3; margin: 30px 0 15px 0;">')
            for line in lines:
                html_parts.append(
                    f'''    <p style="text-align: center; color: {SUB_TEXT_COLOR}; font-size: 13px; margin-bottom: 8px;">{_format_inline(line)}</p>'''
                )

        # 普通段落
        else:
            html_parts.append(
                f'''    <p style="margin-bottom: 14px; color: {TEXT_COLOR}; {JUSTIFY_STYLE}">{_format_inline(block).replace(chr(10), "<br/>")}</p>'''
            )

    if in_abstract:
        if html_parts[-1].startswith('    <p style="margin-bottom: 10px;'):
            html_parts[-1] = html_parts[-1].replace('margin-bottom: 10px;', 'margin-bottom: 0;')
        html_parts.append('    </section>')

    html_parts.append('</section>')
    return '\n'.join(html_parts)


# =========================
# 执行入口
# =========================
if __name__ == "__main__":
    input_file = "test.md"
    output_file = "output.html"

    print("=========================================")
    print("      璇玑枢公众号一键排版工具 v2.2      ")
    print("   (微信友好结构：修复空装饰线被清洗)   ")
    print("=========================================\n")

    if not os.path.exists(input_file):
        print(f"❌ 找不到文件！请在当前目录下创建一个名为【{input_file}】的文件，并写入Markdown内容。")
    else:
        with open(input_file, "r", encoding="utf-8") as f:
            md_content = f.read()

        final_html = md_to_xuanji_html(md_content)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_html)

        print("✅ 转换成功！")
        print(f"👉 请打开生成的【{output_file}】文件，全选代码粘贴到公众号后台。")
