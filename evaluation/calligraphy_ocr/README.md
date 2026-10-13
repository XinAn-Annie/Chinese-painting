# 书法 OCR 基线评测

这里把“文字没有被检测到”和“已经裁切但识别错误”分开测量。

准备脚本使用 7-Zip 解压 HCSU 官方 AES ZIP，并在解压前检查路径穿越。

## 数据边界

- 固定测试集使用 HCSU 的真实书法单字；原目录给出楷、隶、行、草书体，文件名给出字符标签。
- HCSU 数据采用 CC BY-NC 4.0，只能用于非商业研究。
- 固定测试集不得再混入微调训练集，否则评测会发生数据泄漏。
- CalliTrain 后续用于构造训练集和整页/文本行验证集，不替代这个固定测试集。

## 1. 构造固定测试集

```powershell
python prepare_hcsu_benchmark.py `
  --source-root "D:\codex\书法识别资源\datasets\HCSU" `
  --output-root "D:\codex\书法识别资源\benchmarks\hcsu_4styles_100" `
  --per-style 100
```

## 2. 先测纯识别模型

这一步输入已经裁切好的单字，只回答 `PP-OCRv5_server_rec` 能不能识字；所有错误都属于识别错误。

```powershell
python run_ppocrv5_baseline.py `
  --manifest "D:\codex\书法识别资源\benchmarks\hcsu_4styles_100\manifest.csv" `
  --output-dir "D:\codex\书法识别资源\benchmarks\hcsu_4styles_100\baseline"
```

## 3. 再测完整 OCR

完整模式先检测文字框再识别。无框记为 `detection_error`，有框但文字错误记为 `recognition_error`。

```powershell
python run_ppocrv5_baseline.py `
  --manifest "D:\codex\书法识别资源\benchmarks\hcsu_4styles_100\manifest.csv" `
  --output-dir "D:\codex\书法识别资源\benchmarks\hcsu_4styles_100\baseline" `
  --mode system
```

脚本逐条追加 CSV，中断后用同一个命令可以续跑。
