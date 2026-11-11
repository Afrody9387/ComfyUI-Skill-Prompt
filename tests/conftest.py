from pathlib import Path
import sys


# Run tests with ComfyUI's Python, including a normal (non-portable) installation.
comfy_root = Path(__file__).resolve().parents[3]
if (comfy_root / "comfy_api").is_dir():
    sys.path.insert(0, str(comfy_root))
