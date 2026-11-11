"""Install the official, separately licensed H3 prompt skill from its upstream sources."""
import hashlib
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import urlopen


REVISION = "199b7d0e1fd95e7b3eafa8c15eca692534142427"
BASE_URL = f"https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/{REVISION}/skills/h3-prompt-writing/"
LICENSE_URL = "https://huggingface.co/MiniMaxAI/MiniMax-H3/resolve/0919fb684102ef115126612f3fbb84d1027e7317/LICENSE"
SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "h3-prompt-writing"
FILES = {
    "SKILL.md": (BASE_URL + "SKILL.md", "a7000443588ca3f145e3b3fd8900f14e0325dc460bd811268fac89a9dc8e56d0"),
    "agents/openai.yaml": (BASE_URL + "agents/openai.yaml", "7770c9d784b7251ab882ee29a738219a3f01811e57ba7fc7822fa83eb8438c1a"),
    "references/base-en.txt": (BASE_URL + "references/base-en.txt", "2cfebc096a6e08370f288d468d90b60f7f9bcb938f94bf090816e910e48e75fc"),
    "references/ref-en.txt": (BASE_URL + "references/ref-en.txt", "1e574f356716ad55612247ffb7bbccbcdb484ad96599d63c7dca1af186b1fab7"),
    "LICENSE": (LICENSE_URL, "59b99642b95ea21630e311198ddbfffbfe05aadba0c2f5d884cbdf4efcc90f44"),
}
NOTICE = (
    "MiniMax H3 is licensed under the MiniMax H3 Community License Agreement, "
    "Copyright © 2026 MiniMax. All Rights Reserved.\n"
)


def install_skill():
    print("Source: https://github.com/MiniMax-AI/MiniMax-H3/tree/" + REVISION + "/skills/h3-prompt-writing")
    print("License (includes territorial and redistribution terms): " + LICENSE_URL)
    downloads = {}
    for name, (url, checksum) in FILES.items():
        with urlopen(url, timeout=30) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != checksum:
            raise RuntimeError(f"Checksum mismatch: {name}; no files were installed.")
        downloads[name] = content
    downloads["NOTICE"] = NOTICE.encode("utf-8")
    # Preserve a user's existing edits and check all conflicts before writing anything.
    for name, content in downloads.items():
        destination = SKILL_DIR / name
        if destination.exists() and destination.read_bytes().replace(b"\r\n", b"\n") != content.replace(b"\r\n", b"\n"):
            raise RuntimeError(f"Existing file differs and was preserved: {destination}; no files were installed.")
    for name, content in downloads.items():
        destination = SKILL_DIR / name
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    print("Installed: " + str(SKILL_DIR))
    print("Refresh the ComfyUI browser page, then open examples/video_prompt.json.")


if __name__ == "__main__":
    try:
        install_skill()
    except (OSError, URLError, RuntimeError) as exc:
        print("Installation failed: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
