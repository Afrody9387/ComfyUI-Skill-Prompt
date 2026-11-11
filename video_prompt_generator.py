"""Skill-driven video prompt writing with labeled keyframes and sampled video frames."""
import math

from comfy_api.latest import io

from .skill_prompt_generator import (
    SkillPromptGenerator, _NO_SKILLS, _REFERENCE_MODES, _image_parts, discover_skills,
    invoke_with_timeout, load_skill_context,
)

_TASKS = {
    "t2v": "Text-to-video: describe the scene, action, camera movement and changes over time.",
    "i2v_first": "Animate from the supplied first frame. Treat it as the opening state; preserve its identity and scene.",
    "i2v_first_last": "Describe a continuous, plausible transition from the first frame to the last frame.",
    "i2v_last": "Describe motion that converges to the supplied last frame as the final state.",
    "reference": "Use the reference subjects, images and video motion as requested, keeping reference identities distinct.",
    "s2v": "Use the reference images to preserve subject identity while creating the requested action and setting.",
}


def _sample_indices(total, count):
    if total <= 0:
        return []
    count = max(1, min(int(count), total))
    if count == 1:
        return [total // 2]
    return [round(i * (total - 1) / (count - 1)) for i in range(count)]


def _frame_count(images):
    if images is None:
        return 0
    return 1 if images.ndim == 3 else len(images)


def _labeled_images(images, label):
    parts = []
    for index, part in enumerate(_image_parts(images), 1):
        parts.extend([{"type": "text", "text": f"{label} {index}:"}, part])
    return parts


class SkillVideoPromptGenerator(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        skills = list(discover_skills()) or [_NO_SKILLS]
        default_skill = "example-video" if "example-video" in skills else skills[0]
        return io.Schema(
            node_id="SkillVideoPromptGenerator",
            display_name="Skill Video Prompt Generator · 视频 Skill 提示词生成器",
            category="Skill Prompt",
            description="用本地 skill 生成视频提示词，支持关键帧、参考图片、参考视频抽帧。此节点输出文字，不生成视频。",
            inputs=[
                io.Custom("LLMServiceConnector").Input("llm_service_connector"),
                io.Combo.Input("task_type", options=list(_TASKS), default="t2v",
                               tooltip="t2v 文生视频；i2v_first 首帧；i2v_first_last 首尾帧；i2v_last 尾帧；reference 参考素材；s2v 主体参考。"),
                io.String.Input("input_text", default="", multiline=True, dynamic_prompts=False),
                io.Combo.Input("skill", options=skills, default=default_skill),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF, control_after_generate=True),
                io.Image.Input("first_frame", optional=True),
                io.Image.Input("last_frame", optional=True),
                io.Image.Input("reference_images", optional=True),
                io.Image.Input("reference_video", optional=True,
                               tooltip="接视频加载节点输出的 IMAGE 帧批次，不是视频文件路径。"),
                io.Int.Input("width", default=1280, min=1, max=16384, optional=True),
                io.Int.Input("height", default=720, min=1, max=16384, optional=True),
                io.Float.Input("duration", default=6.0, min=0.1, max=3600.0, step=0.1, optional=True),
                io.String.Input("category", default="none", optional=True,
                                tooltip="可自由填写影片类别或风格，如 cinematic、广告、动画；none 表示不指定。"),
                io.Combo.Input("output_language", options=["en", "zh", "auto"], default="en", optional=True),
                io.Int.Input("caption_sample_frames", default=8, min=1, max=64, optional=True,
                             tooltip="从参考视频帧批次中均匀取样的数量；不是输出视频的帧数。取 1 时选择中间帧。"),
                io.Combo.Input("image_detail", options=["auto", "low", "high"], default="auto", optional=True),
                io.Combo.Input("reference_mode", options=_REFERENCE_MODES, default="referenced_text", optional=True),
                io.String.Input("output_instruction", default="", multiline=True, dynamic_prompts=False, optional=True),
                io.Float.Input("temperature", default=0.4, min=0.0, max=2.0, step=0.05, optional=True),
                io.Int.Input("max_tokens", default=8192, min=64, max=32768, optional=True),
                io.Int.Input("max_context_chars", default=120000, min=1, max=2000000, optional=True),
                io.Int.Input("timeout", default=120, min=1, max=3600, optional=True,
                             tooltip="本节点单次 LLM 请求等待秒数，覆盖连接器默认值，不影响其他节点。"),
            ],
            outputs=[io.String.Output(display_name="video_prompt"), io.String.Output(display_name="skill_context"),
                     io.String.Output(display_name="load_report")],
        )

    @classmethod
    def execute(cls, llm_service_connector, task_type, input_text, skill, seed=0,
                first_frame=None, last_frame=None, reference_images=None, reference_video=None,
                width=1280, height=720, duration=6.0, category="none", output_language="en",
                caption_sample_frames=8, image_detail="auto", reference_mode="referenced_text",
                output_instruction="", temperature=0.4, max_tokens=8192, max_context_chars=120000, timeout=120):
        if task_type not in _TASKS:
            raise ValueError(f"Unknown video task: {task_type}")
        if task_type in ("i2v_first", "i2v_first_last") and not _frame_count(first_frame):
            raise ValueError("此任务需要连接 first_frame 首帧图片。")
        if task_type in ("i2v_last", "i2v_first_last") and not _frame_count(last_frame):
            raise ValueError("此任务需要连接 last_frame 尾帧图片。")
        if task_type == "s2v" and not _frame_count(reference_images):
            raise ValueError("s2v 需要连接 reference_images 主体参考图片。")
        if task_type == "reference" and not (_frame_count(reference_images) or _frame_count(reference_video)):
            raise ValueError("reference 需要连接 reference_images 或 reference_video。")
        context, report = load_skill_context(skill, reference_mode, max_context_chars)
        divisor = math.gcd(width, height)
        metadata = (f"Task: {task_type}\n{_TASKS[task_type]}\n"
                    f"Target duration: {duration:g} seconds\nTarget aspect ratio: {width // divisor}:{height // divisor}\n"
                    f"Target resolution: {width} x {height}\nCategory/style: {category}\n")
        if output_language != "auto":
            metadata += f"Output language: {'Chinese' if output_language == 'zh' else 'English'}\n"
        user = metadata + "\nUser request:\n" + (input_text.strip() or "Write a coherent video prompt for this task and the supplied media.")
        if output_instruction.strip():
            user += "\n\nOutput requirements:\n" + output_instruction.strip()
        parts = []
        for images, label in ((first_frame, "First frame"), (last_frame, "Last frame"),
                              (reference_images, "Reference image")):
            if _frame_count(images):
                parts.extend(_labeled_images(images, label))
        indices = _sample_indices(_frame_count(reference_video), caption_sample_frames)
        if indices:
            frames = reference_video.unsqueeze(0) if reference_video.ndim == 3 else reference_video
            # Select before encoding so long videos don't encode every frame.
            for index, image_part in zip(indices, _image_parts(frames[indices])):
                parts.extend([{"type": "text", "text": f"Reference video frame {index + 1}/{len(frames)} (chronological sample):"}, image_part])
        if image_detail != "auto":
            for part in parts:
                if part["type"] == "image_url":
                    part["image_url"]["detail"] = image_detail
        system = (
            "Write a video-generation prompt using the supplied skill. Select its rules for the requested task. "
            "Follow the skill's output structure and media labeling conventions. Keep first/last keyframes distinct "
            "from free references. Sampled video frames are chronological visual observations; no audio was supplied. "
            "Do not claim to have listened to audio or executed tools. The target duration/resolution describe the "
            "requested output video, not the reference clip. You have no shell, filesystem or browsing tools.\n\n" + context
        )
        result = invoke_with_timeout(llm_service_connector,
            [{"role": "system", "content": system},
             {"role": "user", "content": parts + [{"type": "text", "text": user}] if parts else user}],
            timeout=timeout, seed=seed, temperature=temperature, max_tokens=max_tokens,
        )
        report += f"\nTask: {task_type}\nReference video sampled frames: {[index + 1 for index in indices]}"
        return io.NodeOutput(str(result).strip() if result is not None else "", context, report)

    @classmethod
    def fingerprint_inputs(cls, skill, reference_mode="referenced_text", max_context_chars=120000, **kwargs):
        # The graph already fingerprints text, media and generation settings.
        return SkillPromptGenerator.fingerprint_inputs(skill, reference_mode, max_context_chars, **kwargs)
