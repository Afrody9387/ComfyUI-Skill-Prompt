import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path

import pytest


@pytest.fixture
def installer(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts" / "install_h3_skill.py"
    spec = importlib.util.spec_from_file_location("h3_installer_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contents = {
        "SKILL.md": b"Read `references/base-en.txt` and `references/ref-en.txt`.",
        "references/base-en.txt": b"Base guide fixture.",
        "references/ref-en.txt": b"Reference guide fixture.",
        "LICENSE": b"Upstream license fixture.\n",
    }
    urls = {name: "https://official.test/" + name for name in contents}
    monkeypatch.setattr(module, "FILES", {
        name: (urls[name], hashlib.sha256(content).hexdigest()) for name, content in contents.items()
    })
    monkeypatch.setattr(module, "SKILL_DIR", tmp_path / "h3-prompt-writing")
    monkeypatch.setattr(module, "urlopen", lambda url, timeout: BytesIO(
        next(contents[name] for name in contents if urls[name] == url)))
    return module


def test_install_includes_guides_license_and_notice(installer):
    installer.install_skill()
    assert (installer.SKILL_DIR / "references/base-en.txt").read_bytes() == b"Base guide fixture."
    assert (installer.SKILL_DIR / "references/ref-en.txt").is_file()
    assert (installer.SKILL_DIR / "LICENSE").is_file()
    assert "All Rights Reserved" in (installer.SKILL_DIR / "NOTICE").read_text(encoding="utf-8")
    installer.install_skill()  # Re-running with identical content is safe.


def test_changed_local_file_is_preserved_before_any_writes(installer):
    installer.SKILL_DIR.mkdir()
    (installer.SKILL_DIR / "SKILL.md").write_text("My changes", encoding="utf-8")
    with pytest.raises(RuntimeError, match="preserved"):
        installer.install_skill()
    assert (installer.SKILL_DIR / "SKILL.md").read_text(encoding="utf-8") == "My changes"
    assert not (installer.SKILL_DIR / "LICENSE").exists()


def test_checksum_failure_does_not_install(installer, monkeypatch):
    monkeypatch.setattr(installer, "urlopen", lambda url, timeout: BytesIO(b"tampered"))
    with pytest.raises(RuntimeError, match="Checksum mismatch"):
        installer.install_skill()
    assert not installer.SKILL_DIR.exists()
