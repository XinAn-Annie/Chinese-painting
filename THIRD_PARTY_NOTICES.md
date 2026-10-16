# Third-party notices

`LICENSE` only covers original ArtGenome project code and material for which the
ArtGenome contributors have authority to grant that license. The following
components retain their original licenses. When upstream license files are
downloaded with a model or Python package, those files control if this summary
differs from them.

## Models and datasets

### Qwen2.5-VL-3B-Instruct

- Provider: Alibaba Cloud / Qwen team.
- Model ID: `Qwen/Qwen2.5-VL-3B-Instruct`.
- License used by the configured model release: Qwen RESEARCH LICENSE
  AGREEMENT, non-commercial research or evaluation only.
- The first-start downloader preserves the model's `LICENSE` and `NOTICE` in
  `.models/Qwen2.5-VL-3B-Instruct/`.
- Required notice: `Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT,
  Copyright (c) Alibaba Cloud. All Rights Reserved.`

### PP-OCR and PaddleOCR

- Provider: PaddlePaddle / PaddleOCR.
- Components include `PP-OCRv5_server_rec`, `PP-OCRv6_medium_det` and
  `PP-LCNet_x1_0_textline_ori`.
- License: Apache License 2.0. Refer to the license files supplied by the
  upstream PaddleOCR and PaddlePaddle distributions.

### HCSU-derived fallback recognizer

- Dataset: `Tongji209/HCSU`.
- Dataset license recorded by the evaluation pipeline: Creative Commons
  Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
- The derived recognizer is used only to recheck low-confidence single Chinese
  characters and must remain non-commercial. Redistribution must retain HCSU
  attribution and the CC BY-NC 4.0 notice.
- The HCSU source dataset is not included in this repository.

### Inscription detector

- `mcp_services/inscription_detector/models/inscription_detector_best.pt` is a
  project-trained weight used only to locate inscription regions.
- It does not recognize text. The training dataset is not distributed in this
  repository. The model is distributed for the same non-commercial research
  and evaluation purposes as the project code.

## Runtime libraries

- uv: dual-licensed under the MIT License or Apache License 2.0. The launcher
  downloads `uv` from Astral's official installer into `.bootstrap/` and does
  not add it to the system `PATH`.
- The project-specific Python 3.12 runtime is obtained by uv from Astral's
  `python-build-standalone` distributions. CPython remains licensed under the
  Python Software Foundation License; bundled libraries retain their upstream
  licenses.
- Ultralytics: AGPL-3.0 unless a separate Ultralytics enterprise license has
  been obtained.
- Transformers: Apache License 2.0.
- PaddleOCR and PaddlePaddle: Apache License 2.0.
- Flask: BSD-3-Clause.
- Plotly.js 2.26.0: MIT License. The vendored file retains its copyright and
  license header.
- Other Python transitive dependencies retain the licenses included in their
  installed package metadata.

The Python environment is created on the user's computer and is not committed
to this repository or bundled into the source ZIP.

## Fonts

The bundled JiangChengHeiTi 400W, 500W and 700W font files identify themselves
as derived from Adobe Source fonts and licensed under the SIL Open Font License
1.1. Their embedded copyright and license metadata must be retained.

## Example paintings and interface images

The current hashed files under `web_demo/assets/` do not contain a complete
human-readable provenance manifest. Before making the repository public, add
the title, creator, source institution or URL, public-domain/copyright status
and any required attribution for every example painting and non-original image.
Until that manifest is complete, these images must not be assumed to be
licensed for unrestricted redistribution merely because they are present in
the working tree.

## No license expansion

Nothing in the ArtGenome project license grants rights that an upstream model,
dataset, font, image or dependency license does not grant. Commercial users
must independently obtain every required commercial license.
