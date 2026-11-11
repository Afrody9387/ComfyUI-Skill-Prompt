"""Skill loading and multimodal generation, without a paid LLM call."""
import asyncio
import base64
import importlib
from io import BytesIO
from pathlib import Path
import sys
import types

from aiohttp import web
import pytest
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(scope="module")
def skill_module():
    return importlib.import_module("comfyui_skill_prompt.skill_prompt_generator")


def test_standalone_extension_registration(skill_module, monkeypatch):
    plugin = importlib.import_module("comfyui_skill_prompt")
    routes = web.RouteTableDef()
    monkeypatch.setitem(sys.modules, "server", types.SimpleNamespace(
        PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=routes))))
    extension = asyncio.run(plugin.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [skill_module.SkillPromptGenerator, plugin.SkillVideoPromptGenerator, plugin.SkillLLMServiceConnector]
    assert skill_module.SkillPromptGenerator.GET_SCHEMA().node_id == "SkillPromptGenerator"
    assert {route.path for route in routes} == {"/skill-prompt/models", "/skill-prompt/test"}
    assert plugin.WEB_DIRECTORY == "./web"


@pytest.fixture
def skill_dir(tmp_path):
    root = tmp_path / "skills" / "example"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: example\ndescription: metadata only\n---\n"
        "Rewrite the prompt. Read `references/rules.md`.\n"
        "[same rules](references/rules.md#details)\n"
        "[external](https://example.com/private.md)\n",
        encoding="utf-8-sig",
    )
    (root / "references" / "rules.md").write_text("Use concrete nouns. See [more](more.txt).", encoding="utf-8")
    (root / "references" / "more.txt").write_text("Use English. See [root](../SKILL.md).", encoding="utf-8")
    (root / "references" / "unused.md").write_text("Unused rule.", encoding="utf-8")
    (root / "references" / "do_not_run.py").write_text("raise RuntimeError('must not execute')", encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def local_skill_library(skill_module, skill_dir, monkeypatch):
    monkeypatch.setattr(skill_module, "_SKILLS_DIR", skill_dir.parent)


def test_loads_references_recursively_without_metadata_duplicates_or_scripts(skill_module, skill_dir):
    context, report = skill_module.load_skill_context("example")
    assert "metadata only" not in context
    assert context.count("Use concrete nouns") == 1
    assert "Use English" in context
    assert "Unused rule" not in context
    assert "raise RuntimeError" not in context
    assert "Missing reference" not in report
    assert "references/more.txt" in report


def test_reference_modes(skill_module, skill_dir):
    context, _ = skill_module.load_skill_context("example", "skill_only")
    assert "Use concrete nouns" not in context
    context, _ = skill_module.load_skill_context("example", "all_references")
    assert "Unused rule" in context
    assert "raise RuntimeError" not in context


def test_outside_missing_and_encoded_paths(skill_module, skill_dir):
    (skill_dir.parent / "private.txt").write_text("PRIVATE CONTENT", encoding="utf-8")
    (skill_dir / "references" / "with space.md").write_text("spaced reference", encoding="utf-8")
    with (skill_dir / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("\n`../private.txt` `references/missing.md` [space](references/with%20space.md)")
    context, report = skill_module.load_skill_context("example")
    assert "PRIVATE CONTENT" not in context
    assert "Outside skill folder" in report
    assert "Missing reference" in report
    assert "spaced reference" in context


def test_limits_and_invalid_inputs(skill_module, skill_dir):
    with pytest.raises(ValueError, match="max_context_chars"):
        skill_module.load_skill_context("example", max_context_chars=25)
    with pytest.raises(ValueError, match="Unknown reference mode"):
        skill_module.load_skill_context("example", "unknown")
    with pytest.raises(ValueError, match="Skill 不存在"):
        skill_module.load_skill_context("missing")


def test_dropdown_discovers_local_skills_and_rejects_forged_choice(skill_module, skill_dir, monkeypatch):
    assert skill_module.discover_skills() == {"example": skill_dir / "SKILL.md"}
    schema = skill_module.SkillPromptGenerator.define_schema()
    skill_input = next(item for item in schema.inputs if item.id == "skill")
    assert skill_input.options == ["example"]
    assert all(item.id != "skill_path" for item in schema.inputs)
    assert skill_module._selected_skill_path("example") == skill_dir / "SKILL.md"
    for choice in ("../../private", str(skill_dir / "SKILL.md"), "Agents / example"):
        with pytest.raises(ValueError, match="Skill 不存在"):
            skill_module.load_skill_context(choice)


def test_empty_library_has_actionable_placeholder(skill_module, tmp_path, monkeypatch):
    monkeypatch.setattr(skill_module, "_SKILLS_DIR", tmp_path / "empty")
    assert skill_module.discover_skills() == {}
    schema = skill_module.SkillPromptGenerator.define_schema()
    skill_input = next(item for item in schema.inputs if item.id == "skill")
    assert skill_input.options == [skill_module._NO_SKILLS]
    with pytest.raises(ValueError, match="SKILL.md"):
        skill_module.load_skill_context(skill_module._NO_SKILLS)


def test_symlink_cannot_add_external_skill(skill_module, skill_dir):
    outside = skill_dir.parent.parent / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("External rules", encoding="utf-8")
    try:
        (skill_dir.parent / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows privileges")
    assert "linked" not in skill_module.discover_skills()


def test_reference_edit_invalidates_cache(skill_module, skill_dir):
    params = {"skill": "example"}
    before = skill_module.SkillPromptGenerator.fingerprint_inputs(**params)
    (skill_dir / "references" / "more.txt").write_text("Changed rule.", encoding="utf-8")
    assert skill_module.SkillPromptGenerator.fingerprint_inputs(**params) != before


class FakeConnector:
    def invoke(self, messages, **kwargs):
        self.messages = messages
        self.kwargs = kwargs
        return "  final prompt  "


def test_text_generation_uses_existing_connector(skill_module, skill_dir):
    connector = FakeConnector()
    output = skill_module.SkillPromptGenerator.execute(
        connector, "一只红色小鸟", "example",
        output_instruction="Only the prompt.", seed=42, max_tokens=1024,
    )
    assert output[0] == "final prompt"
    assert "Use concrete nouns" in connector.messages[0]["content"]
    assert connector.messages[1]["content"] == "一只红色小鸟\n\nOutput requirements:\nOnly the prompt."
    assert connector.kwargs["seed"] == 42
    assert connector.kwargs["max_tokens"] == 1024
    assert "Loaded files:" in output[2]


def test_oversized_file_is_not_truncated_after_removing_frontmatter(skill_module, skill_dir):
    (skill_dir / "SKILL.md").write_text("---\nname: example\n---\n" + "x" * 110, encoding="utf-8")
    with pytest.raises(ValueError, match="max_context_chars"):
        skill_module.load_skill_context("example", max_context_chars=120)


def test_image_generation_forwards_source_and_references(skill_module, skill_dir):
    connector = FakeConnector()
    skill_module.SkillPromptGenerator.execute(
        connector, "Describe these images", "example",
        source=torch.zeros(1, 8, 8, 3), reference_images=torch.ones(2, 8, 8, 3),
    )
    content = connector.messages[1]["content"]
    assert sum(part["type"] == "image_url" for part in content) == 3
    assert any(part["type"] == "text" and "Describe these images" in part["text"] for part in content)
    images = [part for part in content if part["type"] == "image_url"]
    pixels = []
    for part in images:
        url = part["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        with Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1]))) as image:
            assert image.size == (8, 8)
            pixels.append(image.getpixel((0, 0)))
    assert pixels == [(0, 0, 0), (255, 255, 255), (255, 255, 255)]
