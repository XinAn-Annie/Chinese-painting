# 本地国画赏析与知识讲解服务

该服务默认在本机加载 `Qwen2.5-VL-3B-Instruct`，直接根据上传画面生成审慎分析，不把知识库问答内容交给模型。模型回答完成后，服务只使用受控术语表做确定性的术语规范化；颜色描述则严格受上方颜色识别结果约束。网页只把图片发送到本机 `127.0.0.1:8000`，不需要 API Key。本项目和随项目提供的 Qwen 备用权重仅用于非商业研究、学习与评估。

## 默认本机路径

- 模型：项目根目录的 `.models/Qwen2.5-VL-3B-Instruct`
- 知识库：项目根目录的 `data/sample_qa_check.tsv`（仅在显式启用知识库时使用）
- 受控术语表：`terminology_glossary.json`（当前 33 项）
- 传统色数据库：`..\color_namer\color_database.json`（427 条记录，去重并过滤空值后作为服务端合法名称集合）
- 服务：项目根目录的 `mcp_services/zhihua`

有 CUDA GPU 时服务会自动使用 GPU，并在显存不足时把部分权重卸载到系统内存；没有可用 GPU 时会使用 CPU。第一次赏析会先加载约 7.5 GB 权重，耗时明显长于后续请求。

## 启动

普通用户直接双击项目根目录的 `启动画基因.bat`。首次运行会创建虚拟环境、安装依赖，并优先从 ModelScope 自动下载模型；如果 ModelScope 失败，下载器会自动切换到 GitHub Release 分卷，支持续传、逐卷 SHA256 校验、合并和整文件复核。若只调试知画服务，可在首次安装完成后运行：

```powershell
cd .\mcp_services\zhihua
.\start_local.ps1
```

服务启动后访问 `http://127.0.0.1:8000/services/zhihua/api/health`。正常状态应显示：

- `backend: local`
- `knowledge_enabled: false`
- `terminology_entries: 33`
- `color_vocabulary_entries`：传统色合法名称数量
- `ok: true`

随后打开 `web_demo/index.html`，上传画作并点击“请知画赏析”。

`POST /api/appreciate` 会在赏析正文之外返回 `techniques`：其中 `scores` 固定包含白描、工笔、写意、泼墨、没骨五项，服务端校验并归一化为总计 100%；`evidence` 保存模型给出的简短画面依据。`available: false` 表示模型本次未返回完整的结构化评分，网页会保留正文并显示重试提示。

## 可选配置

可通过环境变量调整：

- `ZHIHUA_MAX_TOKENS`：首次分析最大新 token 数，默认 512。
- `ZHIHUA_FOLLOWUP_MAX_TOKENS`：追加提问最大新 token 数，默认 512。
- `ZHIHUA_CONTINUATION_MAX_TOKENS`：检测到截断或残句时自动续写的最大新 token 数，默认 192。
- `ZHIHUA_USE_KB=1`：重新启用 `ZhiHua_QA` 检索；默认关闭。
- `ZHIHUA_RAG_TOP_K`：检索知识条数，默认 3。
- `ZHIHUA_MODEL_PATH`：覆盖本地模型目录。
- `ZHIHUA_MODEL_SOURCE=auto|modelscope|github`：选择模型下载源；默认 `auto`，即 ModelScope 失败后切换 GitHub。
- `ZHIHUA_GITHUB_MODEL_BASE_URL`：覆盖 GitHub Release 分卷的基础地址。
- `ZHIHUA_KB_PATH`：覆盖知识库 TSV 路径。
- `ZHIHUA_GLOSSARY_PATH`：覆盖受控术语 JSON 路径。
- `ZHIHUA_COLOR_DB_PATH`：覆盖用于校验颜色名称的传统色 JSON 路径。
- `ZHIHUA_BACKEND=remote`：切换回远程 OpenAI 兼容接口，同时配置 `ZHIHUA_BASE_URL`、`ZHIHUA_API_KEY` 和 `ZHIHUA_MODEL`。

## 受控术语规范化

`terminology_glossary.json` 只保留技法名、简明定义和可见证据规则，不包含作品名、作者、年代、寓意或鉴定结论。服务不会用词表反过来提示模型“画面里应该有什么”，而是在模型完成观察后检查回答文本；只有一个术语的全部证据组都已在原回答中出现，才会在文末追加“术语规范化”。例如，模型必须同时描述山体、长而柔韧的皴擦线条和纹理证据，系统才会标注“披麻皴倾向”。没有足够证据时保持零命中，不强行添加术语。如果模型自行说出受控术语却没有满足证据规则，相关断言会从展示正文中移除，并记录在响应的 `terminology.rejected_terms` 中。

词表的资料来源、术语分组和纳入边界见 `terminology_sources.md`。JSON 顶层 `references` 保存来源地址，新增词条通过 `source_refs` 指向对应来源，便于后续复核。

这是一层保守的名称映射，不是对真实创作步骤的鉴定。原始视觉描述会被保留，技术判断使用“倾向”等措辞，便于用户核对术语与画面依据。

## 颜色名称约束

网页只有在完成上方颜色分析后才允许点击“请知画赏析”，并把本幅画已经匹配出的传统色中文名作为 `allowed_colors` 数组提交。服务端会再次用项目内传统色数据库校验，清单外名称不会成为允许值。

模型提示词与输出后处理共同执行以下规则：

- 赏析只能出现本幅画颜色识别阶段已经返回的传统色名。
- 每个颜色统一写成“推测为XX色”；名称本身以“色”结尾时不重复添加。
- 普通的“红色、浅灰色、米白色”等表述，以及清单外传统色所在的语句会被过滤。
- 没有收到颜色识别结果时，回答不得出现具体颜色名。
- `青绿设色`、`浅绛设色`、`小青绿`等名称本身包含颜色判断的术语不会自动追加，避免绕过颜色清单。

接口响应的 `colors.allowed_names` 是本次允许清单，`colors.allowed_phrases` 是规范表述，`colors.removed_claims` 记录被过滤的越界颜色语句。

## 边界

默认提示词要求模型只描述画面中实际可见的物象、位置、颜色、线条、墨色与空间关系，不主动补充象征寓意或作者意图。术语层只处理模型已经写出的可见证据。输出用于学习与知识讲解，不用于真伪鉴定、作者确认或价格评估。
