import unittest

from check_word_counts import classify_count, count_words


class CountTests(unittest.TestCase):
    def test_counts_han_and_ascii_tokens(self):
        self.assertEqual(count_words("# 标题\n你好，AI Agent 2026 long-form!"), 8)

    def test_ignores_code_markup_comments_and_link_urls(self):
        text = "正文 [来源](https://example.com/path)\n\n```py\nfake text\n```\n<!-- hidden -->"
        self.assertEqual(count_words(text), 4)


class ThresholdTests(unittest.TestCase):
    def test_hard_minimum_and_optional_maximum(self):
        self.assertEqual(classify_count(999, 1000), "SHORT")
        self.assertEqual(classify_count(1000, 1000), "PASS")
        self.assertEqual(classify_count(1200, 1000, 1100), "OVER")


if __name__ == "__main__":
    unittest.main()
