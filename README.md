# ComfyUI Skill Prompt

在 ComfyUI 中读取本地 `SKILL.md` 和参考文档，用 LLM 编写图片或视频提示词。连接器、图片版、视频版在同一个插件内，可独立安装使用。

Local skill-driven image and video prompt writing for ComfyUI, with a simple OpenAI-compatible LLM connector. This plugin writes prompts; it does not generate images or videos itself.

## 安装

需要支持 V3 自定义节点的近期 ComfyUI，Python 3.10 或更新版本。在 `ComfyUI/custom_nodes` 下运行：

```sh
git clone https://github.com/Afrody9387/ComfyUI-Skill-Prompt.git comfyui_skill_prompt
python -m pip install -r comfyui_skill_prompt/requirements.txt
```

使用运行 ComfyUI 的 Python。Windows 便携版可在便携包根目录安装依赖：

```powershell
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\comfyui_skill_prompt\requirements.txt
```

也可下载仓库 ZIP，将内容解压到 `ComfyUI/custom_nodes/comfyui_skill_prompt`。该目录应直接包含 `__init__.py`，避免多套一层目录。

重启 ComfyUI、刷新浏览器，在 **Skill Prompt** 分类找到：

| 节点 | 用途 |
| --- | --- |
| Simple LLM Connector · 简洁 LLM 连接器 | 设置地址、密钥和模型，获取模型列表、测试连接 |
| Skill Prompt Generator · Skill 提示词生成器 | 根据文字和可选图片编写图片提示词 |
| Skill Video Prompt Generator · 视频 Skill 提示词生成器 | 根据文字、首尾帧、参考图片或视频帧编写视频提示词 |

## 快速开始与示例工作流

将 [图片示例工作流](examples/image_prompt.json) 或 [视频示例工作流](examples/video_prompt.json) 拖进 ComfyUI。

图片示例使用随包提供的 **Qwen Image 2.1** skill；视频示例使用 **MiniMax H3 官方** skill。首次使用视频示例时，在插件目录运行下面命令，从官方地址安装 H3 skill 与许可文件，然后刷新浏览器：

```sh
python scripts/install_h3_skill.py
```

Windows 便携版也可在便携包根目录运行：

```powershell
.\python_embeded\python.exe .\ComfyUI\custom_nodes\comfyui_skill_prompt\scripts\install_h3_skill.py
```

1. 在连接器填写 `base_url` 和 `api_key`。例如 Venice 为 `https://api.venice.ai/api/v1`，SiliconFlow 为 `https://api.siliconflow.cn/v1`，本地兼容接口可填 `http://127.0.0.1:1234/v1`。也接受完整 `/chat/completions` 地址。
2. 点击 **获取模型**，搜索并选择模型；也可直接填写 `model`。服务未实现 `/models` 时，手动填写模型 ID 即可。
3. 点击 **测试连接（发送短请求）**，查看实际回复及耗时。这会使用少量模型额度，无需运行整个工作流。
4. 在图片或视频节点填写要求，选择 skill，按需调整 `timeout`，运行后在内置 **Preview as Text** 节点查看结果。

示例仅需本插件和 ComfyUI 内置节点，不需要模型文件或其他插件。API 密钥和模型名留空，使用前请填写自己的服务信息。

图片示例默认是文字输入：添加内置 **Load Image**，将它接到 `source` 或 `reference_images`，即可看图编写提示词。使用图片或视频帧时，需要支持视觉的 LLM。

视频示例默认是 `t2v`：接入首帧后将 `task_type` 改为 `i2v_first`；接入首尾帧后改为 `i2v_first_last`。实际视频生成节点接收最终的 `video_prompt` 文本。

## Skills 单独管理

节点只读取本插件自己的 `skills` 目录。放入完整的 skill 文件夹，保留参考文档与原作者许可：

```text
comfyui_skill_prompt/
  skills/
    qwen-image-2-1/         # 随包附带的 Qwen Image 2.1 社区 skill
      SKILL.md
      references/...
      LICENSE
    h3-prompt-writing/     # 运行安装脚本后，从官方获取到本地
      SKILL.md
      references/base-en.txt
      references/ref-en.txt
      LICENSE
    your-own-skill/
      SKILL.md
      references/...
```

下拉菜单显示子文件夹名称。新增/删除 skill 后刷新浏览器；修改现有文件后重新运行即可，内容变更会使缓存失效。
个人 skill 默认被 Git 忽略，不随代码提交；只有明确附带的示例 skill 纳入仓库。原有 `example-image` 和 `example-video` 基础 skill 保留，已有工作流仍可继续使用。各示例的来源与许可见文末。

| 参考资料模式 | 行为 |
| --- | --- |
| `referenced_text`（默认） | 递归读取正文引用的本地文本，支持 Markdown 链接、行内代码路径和普通相对路径 |
| `all_references` | 额外读取选中 skill 的 `references` 下所有文本 |
| `skill_only` | 仅读取 `SKILL.md` 正文 |

引用限定在选中的 skill 文件夹内；跳过的外部路径或缺失文件列在 `load_report`。支持 `.md`、`.txt`、`.json`、`.yaml`、`.yml`、`.csv`、`.toml`、`.rst`。
这是文档规则加载器，不是完整 agent 运行时，不执行 skill 中的脚本、工具或网络抓取。

## 视频节点

| `task_type` | 用途 | 需要的素材 |
| --- | --- | --- |
| `t2v` | 文生视频提示词 | 文字要求；可额外提供视觉灵感 |
| `i2v_first` | 从首帧发展动作 | `first_frame` |
| `i2v_first_last` | 首帧到尾帧的连续过渡 | `first_frame`、`last_frame` |
| `i2v_last` | 运动最终到达尾帧 | `last_frame` |
| `reference` | 综合参考素材 | `reference_images` 或 `reference_video` |
| `s2v` | 保持主体身份、编写新动作 | `reference_images` |

- `reference_video` 接视频加载器输出的 **IMAGE 帧批次**，不接视频路径。插件均匀取样后才编码图片，避免把整个长视频发给 LLM。
- `caption_sample_frames` 是参考视频取样数量，不是输出视频帧数；取 1 时使用中间帧。
- 首帧、尾帧、参考图片、视频取样帧分别标记。视频只有画面输入，不包含音频分析。
- `width`、`height`、`duration` 是目标视频元数据，用于编写提示词，不会设置下游视频生成节点。
- `category` 可自由填风格或用途；`output_language` 可选英文、中文或按输入决定。
- 视频版使用所选 skill 的格式；本视频示例选择官方 H3 skill，也可切换到其他视频模型的 skill。

## 等待时间与输出设置

图片版、视频版和连接器都有 `timeout`（默认 120 秒）。**生成节点自己的值优先**，只作用于当前节点，不会改变共用连接器。连接器上的值用于获取模型、测试连接，以及未指定覆盖值的调用。
此值是每次 HTTP 请求的连接/读取超时；服务明确拒绝某参数而触发兼容重试时，总耗时可能更长。

- `output_instruction`：补充输出格式，如“只输出英文正向提示词，不要解释”。留空则遵循 skill。
- `max_tokens`：最大输出预算；推理模型可能需要更高预算才能生成正文。
- `max_context_chars`：加载指南的字符数上限，不是 token 数。超限时报错，不会截断；请根据服务上下文长度调整。
- 图片输出 `prompt`、视频输出 `video_prompt`；另有实际加载的 `skill_context` 和文件清单 `load_report`。

## 接口兼容与更新

支持 **OpenAI Chat Completions 兼容接口**。直接使用输入的 Bearer 密钥，不读取密钥配置文件；本地免密服务可留空。密钥会随普通工作流保存，分享工作流前请清空。
原生 Anthropic、Gemini 等不同协议需对应适配器；也可连接兼容 `LLMServiceConnector` 的第三方连接器。

不固定发送 `response_format`、`top_k` 等附加参数。只有服务明确拒绝某采样参数时才调整重试；不会因超时或服务端错误自动重复生成请求。

Git 安装用户在插件目录运行 `git pull` 后重启 ComfyUI、刷新浏览器即可更新。自己的 skill 请放在其他子文件夹内，不要直接修改随包附带的示例。H3 安装脚本保留已有的不同内容，不会覆盖本地修改。

## Development

```sh
python -m pip install pytest
python -m pytest tests -q
node tests/test_connector_ui.mjs
```

Tests use a local mock API, not paid LLM services. Example workflows are checked against actual node schemas and executed with a mocked API response.

## 示例来源

- **MiniMax H3**：使用 [MiniMax-AI 官方 h3-prompt-writing](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)。官方文档带有单独的 [Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)，因此通过安装脚本从官方获取，不在本仓库镜像分发。
- **Qwen Image 2.1**：使用 [iamyoki/qwen-image-2.1-skill](https://github.com/iamyoki/qwen-image-2.1-skill)，是依据 Qwen 官方提示词规范整理的社区 skill，保留作者署名与 Apache-2.0 许可，不标为阿里官方 skill。

完整版本记录和许可边界见 [THIRD_PARTY.md](THIRD_PARTY.md)。插件代码及原有基础示例为 MIT；第三方 skill 和用户添加的 skill 保留各自许可。
