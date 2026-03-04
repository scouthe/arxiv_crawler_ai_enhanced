MAX_PAPERS_PER_CATEGORY = 10

GROUP_DEFINITIONS = [
    {
        "group_id": "main",
        "keywords": [
            "人工智能(cs.AI:Artificial Intelligence)",
            "计算机视觉和模式识别(cs.CV:Computer Vision and Pattern Recognition)",
            "机器学习(cs.LG:Machine Learning)",
            "图像和视频处理(eess.IV:Image and Video Processing)",
        ],
        "stats_keys": ["ai", "cv", "lg", "iv"],
        "stats_by_title_contains": [("cs.AI", "ai"), ("cs.CV", "cv"), ("cs.LG", "lg"), ("eess.IV", "iv")],
        "summary_tpl": "今日论文合集：cs.AI人工智能{ai}篇，cs.CV计算机视觉和模式识别{cv}篇，cs.LG机器学习{lg}篇，eess.IV图像和视频处理{iv}篇",
        "article_title_tpl": "人工智能，计算机视觉，机器学习， 图像和视频处理论文速递--({date})",
    },
    {
        "group_id": "audio",
        "keywords": ["声音(cs.SD:Sound)", "音频和语音处理(eess.AS:Audio and Speech Processing)"],
        "stats_keys": ["sd", "as"],
        "stats_by_title_contains": [("cs.SD", "sd"), ("eess.AS", "as")],
        "summary_tpl": "今日论文合集：cs.SD声音{sd}篇，eess.AS音频处理{as}篇",
        "article_title_tpl": "声音，音频和语音处理论文速递--({date})",
    },
    {
        "group_id": "hcro",
        "keywords": [
            "人机交互(cs.HC:Human-Computer Interaction)",
            "机器人技术(cs.RO:Robotics)",
            "神经元和认知(q-bio.NC:Neurons and Cognition)",
        ],
        "stats_keys": ["hc", "ro", "nc"],
        "stats_by_title_contains": [("cs.HC", "hc"), ("cs.RO", "ro"), ("q-bio.NC", "nc")],
        "summary_tpl": "今日论文合集：cs.HC人机交互{hc}篇，cs.RO机器人技术{ro}篇，q-bio.NC神经元和认知{nc}篇",
        "article_title_tpl": "人机交互，机器人技术论文速递--({date})",
    },
]

DIGEST_TEMPLATE = "今日最新 Arxiv 论文摘要汇总 ({date})"

TOP_HEADER = '<p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p><section style="text-align: left; line-height: 1.75; font-family: -apple-system-font,BlinkMacSystemFont, Helvetica Neue, PingFang SC, Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei ,Arial,sans-serif; font-size: 16px"><h1 id="0" style="text-align: center; line-height: 1.75; font-family: -apple-system-font,BlinkMacSystemFont, Helvetica Neue, PingFang SC, Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei ,Arial,sans-serif; font-size: 16px; display: table; padding: 0 1em; border-bottom: 2px solid #0F4C81; margin: 2em auto 1em; color: #3f3f3f; font-weight: bold;margin-top: 0" data-heading="true"><strong style="text-align: left; line-height: 1.75; font-family: -apple-system-font,BlinkMacSystemFont, Helvetica Neue, PingFang SC, Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei ,Arial,sans-serif; font-size: inherit; color: #0F4C81; font-weight: bold">璇玑枢，助力学术成长，点亮科研之路</strong></h1></section>'

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

LINK_SECTION = '<section style="text-align: center; margin: 0 auto 30px; line-height: 1.6; font-family: -apple-system-font,BlinkMacSystemFont, Arial,sans-serif; font-size: 15px;"><span style="color: #555;">本文只展示部分论文，全部详情，AI总结请访问，或点击阅读原文</span><br><a href="https://scouthe.github.io/arxiv_crawler_ai_enhanced/" style="color: #0F4C81; text-decoration: underline; font-weight: bold; word-break: break-all;">https://scouthe.github.io/arxiv_crawler_ai_enhanced/</a></section><p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p>'

BOTTOM_FOOTER = '<p style="text-align: center; color: #888; font-size: 14px; margin-top: 20px;">机器翻译由谷歌翻译提供，仅供参考</p><p style="text-align: center; color: #888; font-size: 14px; margin-top: 20px;">点击阅读原文看详细论文内容，AI总结</p>'

IMAGE_URL = "http://mmbiz.qpic.cn/mmbiz_png/pdoYWlyPiaWE88Y687KoLpQPXSw646ISBHAUmLDZ1Hk9YxnuC551yF9ibpLiaLK4NyqNO15icJvZdsic5HqMUNJQwNg/0?wx_fmt=png"

IMAGE_HTML = f'<p style="text-align: center; margin-top: 20px;"><img src="{IMAGE_URL}" style="max-width: 100%; height: auto;"/></p>'

CATEGORY_HEADER_TEMPLATE = '<p style="font-size: 0px; line-height: 0; margin: 0px;">&nbsp;</p><section style="text-align: left; line-height: 1.75; font-family: -apple-system-font,BlinkMacSystemFont, Helvetica Neue, PingFang SC, Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei ,Arial,sans-serif; font-size: 16px"><section data-pm-slice="0 0 []" style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;color: rgba(0, 0, 0, 0.9);font-family: system-ui, -apple-system, BlinkMacSystemFont, Arial, sans-serif;font-size: 17px;font-style: normal;font-variant-ligatures: normal;font-variant-caps: normal;font-weight: 400;letter-spacing: 0.544px;orphans: 2;text-align: justify;text-indent: 0px;text-transform: none;widows: 2;word-spacing: 0px;-webkit-text-stroke-width: 0px;white-space: normal;background-color: rgb(255, 255, 255);text-decoration-thickness: initial;text-decoration-style: initial;text-decoration-color: initial;visibility: visible;;margin-top: 0"><section data-pm-slice="0 0 []" style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;color: rgba(0, 0, 0, 0.9);font-size: 17px;letter-spacing: 0.544px;text-align: justify;text-decoration-thickness: initial;background-color: rgb(255, 255, 255);visibility: visible;font-family: system-ui, -apple-system, BlinkMacSystemFont, Arial, sans-serif;"><section data-role="title" data-tools="135编辑器" data-id="110559" style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;position: relative;letter-spacing: 0.544px;color: rgb(34, 34, 34);visibility: visible;font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif;"><section style="-webkit-tap-highlight-color: transparent;margin: 10px auto 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;text-align: center;visibility: visible;"><section style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;display: flex;justify-content: center;align-items: center;visibility: visible;"><p style="-webkit-tap-highlight-color: transparent;margin: 0px 10px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;clear: both;min-height: 1em;font-size: 16px;letter-spacing: 1px;color: rgb(11, 67, 209);visibility: visible;"><span style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;font-size: 18px;visibility: visible;"><strong data-brushtype="text" style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;visibility: visible;"><span style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box !important;overflow-wrap: break-word !important;visibility: visible;">{{CATEGORY_TITLE}}</span></strong></span></p><section style="-webkit-tap-highlight-color: transparent;margin: 0px;padding: 0px;outline: 0px;max-width: 100%;box-sizing: border-box;overflow-wrap: break-word !important;width: 60px;line-height: 0;flex-shrink: 0;visibility: visible;"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" viewBox="0 0 94.71 22.73" style="visibility: visible;" role="img" aria-label="插图"><g style="visibility: visible;"><rect x="16.18" y="10.86" transform="matrix(-1 5.716437e-11 -5.716437e-11 -1 110.893 22.7254)" style="fill: #72c1f4;visibility: visible;" width="78.53" height="1"></rect><polygon style="fill: #72c1f4;visibility: visible;" points="17.44,3.16 21.2,3.16 15.72,19.56 11.97,19.56"></polygon><polygon style="fill: #ffae28;visibility: visible;" points="7.52,0 13.16,0 5.64,22.73 0,22.73"></polygon></g></svg></section></section></section></section></section></section>'

ARTICLE_TEMPLATE = '<section style="text-align: left;line-height: 1.75;font-family: -apple-system-font,BlinkMacSystemFont, Helvetica Neue, PingFang SC, Hiragino Sans GB , Microsoft YaHei UI , Microsoft YaHei ,Arial,sans-serif;font-size: 16px;"> <p style="margin: 0px;padding: 0px;box-sizing: border-box !important;overflow-wrap: break-word !important;color: black;font-size: 14px;text-align: left;visibility: visible;"> <span style="box-sizing: border-box !important;overflow-wrap: break-word !important;visibility: visible;">{{ENGLISH_TITLE}}</span> </p> <div style="margin-top: 5px; margin-left: 0px; color: #3f3f3f;"> <div style="margin-bottom: 3px;"> <strong style="color: #0F4C81; font-weight: bold;">标题</strong> <span>: {{CHINESE_TITLE}}</span> </div> <div style="margin-bottom: 3px;"> <strong style="color: #0F4C81; font-weight: bold;">链接</strong> <span>: {{ARXIV_LINK}}</span> </div> </div> </section> <section style="margin: 5px auto;padding: 0.5em;box-sizing: border-box;overflow-wrap: break-word !important;font-family: &quot;PingFang SC&quot;, system-ui, -apple-system, BlinkMacSystemFont, &quot;Helvetica Neue&quot;, &quot;Hiragino Sans GB&quot;, &quot;Microsoft YaHei UI&quot;, &quot;Microsoft YaHei&quot;, Arial, sans-serif;font-style: normal;font-weight: 400;background: rgb(240, 240, 240);color: rgb(102, 101, 101);font-size: 14px;line-height: 1.3em;text-align: left;height: 12em;overflow: auto;"> <div style="margin-bottom: 5px;"><span style="font-size: 12px;color:#0F4C81;"><b>作者</b>：{{AUTHORS}}</span></div> <div style="margin-bottom: 5px;"><span style="font-size: 13px;color:#0F4C81;"><b>摘要</b>：{{CHINESE_ABSTRACT}}</span></div> <div><span style="font-size: 13px;color:#0F4C81;"><b>Abstract</b>：{{ENGLISH_ABSTRACT}}</span></div> </section> <p style="font-size: 0px;line-height: 0;margin: 0px;">&nbsp;</p>'

