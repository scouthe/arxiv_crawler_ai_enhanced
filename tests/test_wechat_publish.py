import unittest

from wechat_publish.journal_branch import replace_markdown_images
from wechat_publish.markdown_branches import filter_categories


class WechatPublishTests(unittest.TestCase):
    def test_filter_categories_and_stats(self):
        text = """## 人工智能(cs.AI:Artificial Intelligence)

【1】p1
【2】p2
## 其他分类
【1】x
"""
        group = {
            "keywords": ["人工智能(cs.AI:Artificial Intelligence)"],
            "stats_keys": ["ai"],
            "stats_by_title_contains": [("cs.AI", "ai")],
        }
        filtered, stats = filter_categories(text, group)
        self.assertIn("【1】p1", filtered)
        self.assertNotIn("其他分类", filtered)
        self.assertEqual(stats["ai"], 2)

    def test_replace_markdown_images(self):
        src = "A\n![](a.png)\nB\n![](b.png)\nC"
        out = replace_markdown_images(src, ["u1", "u2"])
        self.assertIn("![](u1)", out)
        self.assertIn("![](u2)", out)

    def test_replace_markdown_images_insufficient(self):
        src = "A\n![](a.png)\nB\n![](b.png)\nC"
        out = replace_markdown_images(src, ["u1"])
        self.assertIn("![](u1)", out)
        self.assertNotIn("b.png", out)


if __name__ == "__main__":
    unittest.main()

