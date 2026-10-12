import json
import unittest

import server


class ColorConstraintTests(unittest.TestCase):
    def test_color_database_is_loaded(self):
        names = server.load_traditional_color_names()
        self.assertGreaterEqual(len(names), 380)
        self.assertIn("朱砂", names)
        self.assertIn("月白", names)

    def test_allowed_colors_must_exist_in_database(self):
        raw = json.dumps(["朱砂", "不存在的颜色", "月白", "朱砂"], ensure_ascii=False)
        self.assertEqual(server.parse_allowed_colors(raw), ["朱砂", "月白"])

    def test_allowed_color_is_normalized_to_required_phrase(self):
        source = "印章呈朱砂色，衣袍接近月白。人物站在画面中央。"
        normalized, removed = server.enforce_color_vocabulary(source, ["朱砂", "月白"])
        self.assertIn("推测为朱砂色", normalized)
        self.assertIn("推测为月白色", normalized)
        self.assertIn("人物站在画面中央", normalized)
        self.assertEqual(removed, [])

    def test_color_name_ending_in_se_is_not_duplicated(self):
        source = "花瓣接近妃色。"
        normalized, removed = server.enforce_color_vocabulary(source, ["妃色"])
        self.assertTrue(normalized.startswith("花瓣接近推测为妃色。"))
        self.assertIn("上方颜色识别结果（不对应具体物象）：推测为妃色。", normalized)
        self.assertNotIn("妃色色", normalized)
        self.assertEqual(removed, [])

    def test_unrecognized_color_claims_are_removed(self):
        source = "衣袍是浅灰色，印章呈朱砂色。人物站在画面中央。整体色调柔和，线条较细。"
        normalized, removed = server.enforce_color_vocabulary(source, ["朱砂"])
        self.assertNotIn("浅灰色", normalized)
        self.assertNotIn("色调柔和", normalized)
        self.assertIn("推测为朱砂色", normalized)
        self.assertIn("人物站在画面中央", normalized)
        self.assertIn("线条较细", normalized)
        self.assertNotIn("，。", normalized)
        self.assertNotIn("。，", normalized)
        self.assertEqual(removed, ["衣袍是浅灰色", "整体色调柔和"])

    def test_no_palette_means_no_specific_color_claim(self):
        source = "背景为米白色，人物线条较细。"
        normalized, removed = server.enforce_color_vocabulary(source, [])
        self.assertNotIn("米白", normalized)
        self.assertIn("人物线条较细", normalized)
        self.assertEqual(removed, ["背景为米白色"])

    def test_invalid_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            server.parse_allowed_colors('{"name":"朱砂"}')


if __name__ == "__main__":
    unittest.main()
