import unittest
import re
import json

import server


class TerminologyNormalizationTests(unittest.TestCase):
    def test_glossary_schema_and_patterns(self):
        with server.GLOSSARY_PATH.open("r", encoding="utf-8") as handle:
            glossary = json.load(handle)
        entries = glossary["entries"]
        references = set(glossary["references"])
        terms = [entry["term"] for entry in entries]
        self.assertEqual(len(entries), 33)
        self.assertEqual(len(terms), len(set(terms)))
        for entry in entries:
            self.assertTrue(entry["definition"])
            self.assertTrue(entry["evidence_groups"])
            for group in entry["evidence_groups"]:
                self.assertTrue(group)
                for pattern in group:
                    re.compile(pattern)
            self.assertTrue(set(entry.get("source_refs", [])) <= references)

    def test_does_not_invent_term_without_technique_evidence(self):
        source = "画面中是一位穿浅色长袍的老人，背景留白。"
        normalized, matches, rejected = server.normalize_terminology(source)
        self.assertEqual(normalized, source)
        self.assertEqual(matches, [])
        self.assertEqual(rejected, [])

    def test_matches_pima_cun_only_with_all_evidence_groups(self):
        source = "山体以长而柔韧的线条顺势皴擦，形成绵密纹理。"
        normalized, matches, rejected = server.normalize_terminology(source)
        self.assertEqual([item["term"] for item in matches], ["披麻皴"])
        self.assertIn("披麻皴倾向", normalized)
        self.assertEqual(rejected, [])

    def test_matches_mogu_from_visible_outline_and_color_evidence(self):
        source = "花叶没有清晰轮廓线，而是直接用颜色成形。"
        normalized, matches, rejected = server.normalize_terminology(source)
        self.assertEqual([item["term"] for item in matches], ["没骨"])
        self.assertIn("没骨法倾向", normalized)
        self.assertEqual(rejected, [])

    def test_does_not_match_pima_cun_from_mountain_alone(self):
        source = "远处可见山体，轮廓较淡。"
        _, matches, _ = server.normalize_terminology(source)
        self.assertNotIn("披麻皴", [item["term"] for item in matches])

    def test_removes_unsupported_controlled_term_from_model_answer(self):
        source = "画作采用了工笔技法，线条较流畅。人物穿浅色长袍。"
        normalized, matches, rejected = server.normalize_terminology(source)
        self.assertNotIn("工笔", normalized)
        self.assertEqual(matches, [])
        self.assertEqual(rejected, ["工笔"])
        self.assertIn("线条较流畅", normalized)

    def test_matches_jiehua_only_with_architecture_and_straight_lines(self):
        source = "画面中的楼阁以粗细均匀的直线组织，平行线十分规整。"
        _, matches, rejected = server.normalize_terminology(source)
        self.assertIn("界画", [item["term"] for item in matches])
        self.assertEqual(rejected, [])

    def test_matches_blank_space_with_functional_subject(self):
        source = "画面右侧保留大片空白，用来表现开阔水面。"
        _, matches, rejected = server.normalize_terminology(source)
        self.assertIn("留白", [item["term"] for item in matches])
        self.assertEqual(rejected, [])

    def test_does_not_label_three_distances_from_mountain_word_alone(self):
        source = "画面中央有一座山峰。"
        _, matches, _ = server.normalize_terminology(source)
        terms = [item["term"] for item in matches]
        self.assertNotIn("平远", terms)
        self.assertNotIn("高远", terms)
        self.assertNotIn("深远", terms)


if __name__ == "__main__":
    unittest.main()
