"""Standalone skill prompt generator using an LLM service connector."""
import base64
import copy
import hashlib
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import unquote

from comfy_api.latest import io
from PIL import Image

__all__ = ["SkillPromptGenerator"]

_TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".toml", ".rst"}
_REFERENCE_MODES = ["referenced_text", "all_references", "skill_only"]
_SKILLS_DIR = Path(__file__).resolve().parent / "skills"
_NO_SKILLS = "（请先在 skills 文件夹中添加 skill）"
_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)")
_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_BARE_PATH = re.compile(r"(?<![\w:/\\.-])(?:[\w.-]+[/\\])*[\w.-]+\.(?:md|txt|json|ya?ml|csv|toml|rst)\b", re.IGNORECASE)


def discover_skills():
    root = _SKILLS_DIR.resolve()
    skills = {}
    for entry in sorted(root.glob("*/SKILL.md")):
        if not entry.parent.name.startswith(".") and entry.is_file() and entry.resolve().is_relative_to(root):
            skills[entry.parent.name] = entry
    return skills


def _selected_skill_path(skill):
    skills = discover_skills()
    if skill not in skills:
        raise ValueError(f"Skill 不存在: {skill}；请在 {_SKILLS_DIR}/<名称>/SKILL.md 添加文件后刷新浏览器。")
    return skills[skill].resolve()


def _text_references(text):
    links = [m.group(1) or m.group(2) for m in _LINK.finditer(text)]
    codes = [m.group(1) for m in _CODE.finditer(text)]
    return links + codes + [m.group(0) for m in _BARE_PATH.finditer(text)]


def load_skill_context(skill, reference_mode="referenced_text", max_context_chars=120000):
    if reference_mode not in _REFERENCE_MODES:
        raise ValueError(f"Unknown reference mode: {reference_mode}")
    if max_context_chars < 1:
        raise ValueError("max_context_chars must be positive.")
    entry = _selected_skill_path(skill)
    root = entry.parent
    queue = [entry]
    if reference_mode == "all_references" and (root / "references").is_dir():
        queue.extend(sorted((root / "references").rglob("*")))
    visited = set()
    sections = []
    loaded = []
    skipped = []
    total = 0
    while queue:
        path = queue.pop(0).resolve()
        if path in visited:
            continue
        visited.add(path)
        if not path.is_relative_to(root):
            skipped.append(f"Outside skill folder: {path}")
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES or path.is_dir():
            continue
        if not path.is_file():
            skipped.append(f"Missing reference: {path.relative_to(root).as_posix()}")
            continue
        with path.open("r", encoding="utf-8-sig") as handle:
            text = handle.read(max_context_chars + 1)
        if len(text) > max_context_chars:
            raise ValueError(f"Skill 文件超过 max_context_chars={max_context_chars}: {path}；请提高限制或减少参考文件。")
        if path == entry:
            text = re.sub(r"\A---\s*\n.*?\n---[^\S\n]*(?:\n|$)", "", text, count=1, flags=re.DOTALL)
            if not text.strip():
                raise ValueError(f"SKILL.md 正文为空: {entry}")
        name = path.relative_to(root).as_posix()
        section = f"### Skill file: {name}\n\n{text.strip()}"
        total += len(section) + (2 if sections else 0)
        if total > max_context_chars:
            raise ValueError(
                f"Skill 文本超过 max_context_chars={max_context_chars}；"
                "请提高限制或改用 skill_only / referenced_text，文本未被截断。"
            )
        sections.append(section)
        loaded.append(name)
        if reference_mode != "skill_only":
            for ref in _text_references(text):
                if "://" in ref or ref.startswith(("#", "mailto:", "data:")):
                    continue
                ref = unquote(ref.split("#", 1)[0].split("?", 1)[0]).replace("\\", "/")
                if Path(ref).suffix.lower() in _TEXT_SUFFIXES:
                    queue.append(path.parent / ref)
    context = "\n\n".join(sections)
    report = f"Skill: {entry}\nMode: {reference_mode}\nCharacters: {len(context)}\nLoaded files:\n"
    report += "\n".join(f"- {name}" for name in loaded)
    if skipped:
        report += "\nSkipped references:\n" + "\n".join(f"- {item}" for item in skipped)
    return context, report


def _image_parts(images):
    frames = images.unsqueeze(0) if images.ndim == 3 else images
    parts = []
    for frame in frames:
        pixels = (frame.detach().cpu().numpy().clip(0, 1) * 255).astype("uint8")
        with BytesIO() as buffer:
            Image.fromarray(pixels).save(buffer, format="PNG")
            url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": url, "detail": "auto"}})
    return parts


class SkillPromptGenerator(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        skills = list(discover_skills()) or [_NO_SKILLS]
        default_skill = next((name for name in ("qwen-image-2-1", "example-image") if name in skills), skills[0])
        return io.Schema(
            node_id="SkillPromptGenerator",
            display_name="Skill Prompt Generator · Skill 提示词生成器",
            category="Skill Prompt",
            description="读取本地 SKILL.md 与引用文本，通过 LLM 生成图片提示词。支持文档规则，不执行 skill 脚本或工具。",
            inputs=[
                io.Custom("LLMServiceConnector").Input("llm_service_connector"),
                io.String.Input("input_text", default="", multiline=True, dynamic_prompts=False),
                io.Combo.Input("skill", options=skills, default=default_skill,
                               tooltip="只读取 comfyui_skill_prompt/skills/<名称>/SKILL.md；新增后刷新浏览器。"),
                io.Combo.Input("reference_mode", options=_REFERENCE_MODES, default="referenced_text",
                               tooltip="referenced_text：递归读取正文引用的本地文本；all_references：额外读取 references 下的所有文本；skill_only：只读主文件。"),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF, control_after_generate=True),
                io.Image.Input("source", optional=True),
                io.Image.Input("reference_images", optional=True),
                io.String.Input("output_instruction", default="", multiline=True, optional=True, dynamic_prompts=False,
                                tooltip="可补充输出格式，例如：只输出英文正向提示词，不要解释。留空则遵循 skill。"),
                io.Float.Input("temperature", default=0.8, min=0.0, max=2.0, step=0.05, optional=True),
                io.Int.Input("max_tokens", default=8192, min=64, max=32768, optional=True),
                io.Int.Input("max_context_chars", default=120000, min=1, max=2000000, optional=True,
                             tooltip="Skill 文本字符数上限（不是 token 数）。超过时提示调整，不会静默截断。"),
                io.Int.Input("timeout", default=120, min=1, max=3600, optional=True,
                             tooltip="本节点单次 LLM 请求等待秒数，覆盖连接器默认值，不影响其他节点。"),
            ],
            outputs=[io.String.Output(display_name="prompt"), io.String.Output(display_name="skill_context"),
                     io.String.Output(display_name="load_report")],
        )

    @classmethod
    def execute(cls, llm_service_connector, input_text, skill, reference_mode="referenced_text", seed=0,
                source=None, reference_images=None, output_instruction="", temperature=0.8, max_tokens=8192,
                max_context_chars=120000, timeout=120):
        context, report = load_skill_context(skill, reference_mode, max_context_chars)
        system = (
            "Apply the following skill to the user's prompt-writing request. "
            "Referenced local text files are included below, identified by their relative paths. "
            "Choose the applicable rules for this request; do not merge mutually exclusive modes. "
            "You have no filesystem, shell, browsing, or tool execution capability in this call. "
            "Do not claim to have executed scripts or tools.\n\n" + context
        )
        user = input_text.strip() or "Generate a prompt following the supplied skill."
        if output_instruction.strip():
            user += "\n\nOutput requirements:\n" + output_instruction.strip()
        parts = []
        if source is not None:
            parts.extend(_image_parts(source))
        if reference_images is not None:
            parts.extend(_image_parts(reference_images))
        if parts:
            user = parts + [{"type": "text", "text": user}]
        result = invoke_with_timeout(llm_service_connector,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            timeout=timeout, seed=seed, temperature=temperature, top_p=0.9, max_tokens=max_tokens,
        )
        return io.NodeOutput(str(result).strip() if result is not None else "", context, report)

    @classmethod
    def fingerprint_inputs(cls, skill, reference_mode="referenced_text", max_context_chars=120000, **kwargs):
        context, report = load_skill_context(skill, reference_mode, max_context_chars)
        return hashlib.sha256((context + "\n" + report).encode("utf-8")).hexdigest()


def invoke_with_timeout(connector, messages, timeout, **kwargs):
    if hasattr(connector, "timeout"):
        request_connector = copy.copy(connector)
        request_connector.timeout = timeout
        return request_connector.invoke(messages, **kwargs)
    return connector.invoke(messages, timeout=timeout, **kwargs)
