import importlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
plugin = importlib.import_module("comfyui_skill_prompt")
connector_module = importlib.import_module("comfyui_skill_prompt.llm_connector")


def workflow_values(node, cls):
    values = iter(node["widgets_values"])
    kwargs = {}
    types = cls.INPUT_TYPES()
    for group in ("required", "optional"):
        for name, definition in types.get(group, {}).items():
            kind = definition[0]
            if kind in ("LLMServiceConnector", "IMAGE"):
                continue
            kwargs[name] = next(values)
            if isinstance(kind, list):
                assert kwargs[name] in kind, (name, kwargs[name])
            if len(definition) > 1 and definition[1].get("control_after_generate"):
                assert next(values) == "fixed"
    assert next(values, None) is None, "Unexpected serialized widget value"
    return kwargs


@pytest.mark.parametrize("filename,cls", [
    ("image_prompt.json", plugin.SkillPromptGenerator),
    ("video_prompt.json", plugin.SkillVideoPromptGenerator),
])
def test_examples_connect_and_run_without_private_content(filename, cls, monkeypatch, tmp_path):
    data = json.loads((ROOT / "examples" / filename).read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in data["nodes"]}
    for link_id, source, slot, target, target_slot, kind in data["links"]:
        assert link_id in nodes[source]["outputs"][slot]["links"]
        assert nodes[target]["inputs"][target_slot]["link"] == link_id
        assert nodes[source]["outputs"][slot]["type"] == kind
    config = workflow_values(nodes[1], plugin.SkillLLMServiceConnector)
    assert config["api_key"] == "" and config["model"] == ""
    config["base_url"] = "https://example.test/v1"
    config["model"] = "test-model"
    expected_skill = "qwen-image-2-1" if filename == "image_prompt.json" else "h3-prompt-writing"
    if filename == "video_prompt.json":
        # A fresh public checkout obtains H3 separately; exercise the node with an installed fixture.
        target = tmp_path / "skills" / expected_skill
        (target / "references").mkdir(parents=True)
        (target / "SKILL.md").write_text("Read `references/base-en.txt`.", encoding="utf-8")
        (target / "references/base-en.txt").write_text("H3 test guide fixture.", encoding="utf-8")
        image_module = importlib.import_module("comfyui_skill_prompt.skill_prompt_generator")
        monkeypatch.setattr(image_module, "_SKILLS_DIR", target.parent)
    generator_values = workflow_values(nodes[2], cls)
    assert generator_values["skill"] == expected_skill
    calls = []
    class Response:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "Example generated prompt"}}]}
    def request(method, url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr(connector_module.requests, "request", request)
    connector = plugin.SkillLLMServiceConnector.execute(**config)[0]
    result = cls.execute(llm_service_connector=connector, **generator_values)
    assert result[0] == "Example generated prompt"
    assert "references/" in result[2]
    assert calls[0][1]["timeout"] == generator_values["timeout"]
    assert connector.timeout == 120
    assert nodes[3]["type"] == "PreviewAny"
