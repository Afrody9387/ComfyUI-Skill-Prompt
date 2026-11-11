import importlib
from pathlib import Path
import sys

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
video = importlib.import_module("comfyui_skill_prompt.video_prompt_generator")
image = importlib.import_module("comfyui_skill_prompt.skill_prompt_generator")


@pytest.fixture(autouse=True)
def skill_library(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    (root / "video").mkdir(parents=True)
    (root / "video" / "SKILL.md").write_text("Write the requested video prompt.", encoding="utf-8")
    monkeypatch.setattr(image, "_SKILLS_DIR", root)


class Connector:
    def __init__(self):
        self.timeout = 12
        self.calls = []

    def invoke(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs, "timeout": self.timeout})
        return " video prompt "


def test_text_video_and_timeout_do_not_mutate_shared_connector():
    connector = Connector()
    result = video.SkillVideoPromptGenerator.execute(
        connector, "t2v", "A bird flies over a lake.", "video", duration=5, width=1920, height=1080,
        output_language="zh", timeout=345,
    )
    assert result[0] == "video prompt"
    assert connector.timeout == 12
    assert connector.calls[0]["timeout"] == 345
    user = connector.calls[0]["messages"][1]["content"]
    assert "16:9" in user and "5 seconds" in user and "Chinese" in user


def test_image_node_timeout_uses_local_override():
    connector = Connector()
    image.SkillPromptGenerator.execute(connector, "a bird", "video", timeout=234)
    assert connector.calls[0]["timeout"] == 234 and connector.timeout == 12


def test_timeout_override_does_not_leak_on_failure():
    class FailingConnector(Connector):
        def invoke(self, *args, **kwargs):
            assert self.timeout == 333
            raise ValueError("failed")
    connector = FailingConnector()
    with pytest.raises(ValueError, match="failed"):
        image.SkillPromptGenerator.execute(connector, "test", "video", timeout=333)
    assert connector.timeout == 12


def test_first_last_and_references_are_labeled():
    connector = Connector()
    video.SkillVideoPromptGenerator.execute(connector, "i2v_first_last", "turn around", "video",
        first_frame=torch.zeros(1, 8, 8, 3), last_frame=torch.ones(1, 8, 8, 3),
        reference_images=torch.zeros(2, 8, 8, 3), image_detail="high")
    parts = connector.calls[0]["messages"][1]["content"]
    labels = [part["text"] for part in parts if part["type"] == "text"]
    assert labels[:4] == ["First frame 1:", "Last frame 1:", "Reference image 1:", "Reference image 2:"]
    assert all(part["image_url"]["detail"] == "high" for part in parts if part["type"] == "image_url")


def test_video_frames_sampled_before_encoding(monkeypatch):
    connector = Connector()
    encoded = []
    original = video._image_parts
    def encode(frames):
        encoded.append(len(frames))
        return original(frames)
    monkeypatch.setattr(video, "_image_parts", encode)
    result = video.SkillVideoPromptGenerator.execute(connector, "reference", "match the motion", "video",
        reference_video=torch.zeros(100, 8, 8, 3), caption_sample_frames=3)
    assert encoded == [3]
    assert "[1, 51, 100]" in result[2]
    parts = connector.calls[0]["messages"][1]["content"]
    assert sum(part["type"] == "image_url" for part in parts) == 3


def test_single_frame_sampling():
    assert video._sample_indices(100, 1) == [50]
    assert video._sample_indices(3, 8) == [0, 1, 2]
    assert video._sample_indices(0, 1) == []


@pytest.mark.parametrize("task,field", [
    ("i2v_first", "first_frame"), ("i2v_first_last", "first_frame"),
    ("i2v_last", "last_frame"), ("s2v", "reference_images"), ("reference", "reference_images"),
])
def test_missing_required_media_is_actionable(task, field):
    with pytest.raises(ValueError, match=field):
        video.SkillVideoPromptGenerator.execute(Connector(), task, "motion", "video")


def test_video_reference_changes_invalidate_cache(tmp_path):
    before = video.SkillVideoPromptGenerator.fingerprint_inputs("video")
    (tmp_path / "skills" / "video" / "SKILL.md").write_text("New instructions.", encoding="utf-8")
    assert before != video.SkillVideoPromptGenerator.fingerprint_inputs("video")
