import json
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from server import TECHNIQUE_LABELS, app, parse_model_response


class TechniqueScoreTests(unittest.TestCase):
    def test_parses_and_normalizes_complete_model_payload(self):
        payload = {
            "analysis": "画面以线条和墨色变化组织空间。",
            "technique_scores": {
                "白描": 10,
                "工笔": 20,
                "写意": 40,
                "泼墨": 20,
                "没骨": 10,
            },
            "technique_evidence": {
                label: f"{label}的可见依据" for label in TECHNIQUE_LABELS
            },
        }
        analysis, techniques = parse_model_response(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(analysis, payload["analysis"])
        self.assertTrue(techniques["available"])
        self.assertEqual(techniques["total"], 100.0)
        self.assertEqual(sum(techniques["scores"].values()), 100.0)
        self.assertEqual(list(techniques["scores"]), list(TECHNIQUE_LABELS))

    def test_accepts_json_code_fence_and_rescales_scores(self):
        payload = {
            "analysis": "仅描述当前画面的可见特征。",
            "technique_scores": {label: 1 for label in TECHNIQUE_LABELS},
            "technique_evidence": {},
        }
        raw = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
        _, techniques = parse_model_response(raw)
        self.assertTrue(techniques["available"])
        self.assertEqual(techniques["scores"], {label: 20.0 for label in TECHNIQUE_LABELS})

    def test_keeps_narrative_when_scores_are_incomplete(self):
        payload = {
            "analysis": "正文仍然可用。",
            "technique_scores": {"白描": 100},
        }
        analysis, techniques = parse_model_response(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(analysis, "正文仍然可用。")
        self.assertFalse(techniques["available"])

    @patch("server.local_inference")
    def test_appreciate_endpoint_returns_techniques(self, mocked_inference):
        mocked_inference.return_value = json.dumps({
            "analysis": "线条疏密与墨色层次构成画面。",
            "technique_scores": {
                "白描": 15,
                "工笔": 25,
                "写意": 35,
                "泼墨": 15,
                "没骨": 10,
            },
            "technique_evidence": {
                label: "依据当前画面可见特征" for label in TECHNIQUE_LABELS
            },
        }, ensure_ascii=False)
        image = BytesIO()
        Image.new("RGB", (32, 32), "white").save(image, "PNG")
        image.seek(0)
        response = app.test_client().post("/api/appreciate", data={
            "image": (image, "painting.png"),
            "allowed_colors": "[]",
        })
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["techniques"]["total"], 100.0)
        self.assertEqual(result["techniques"]["scores"]["写意"], 35.0)


if __name__ == "__main__":
    unittest.main()
