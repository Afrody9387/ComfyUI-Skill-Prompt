from comfy_api.latest import ComfyExtension

from .skill_prompt_generator import SkillPromptGenerator
from .video_prompt_generator import SkillVideoPromptGenerator
from .llm_connector import SkillLLMServiceConnector
from .connector_api import register_routes

WEB_DIRECTORY = "./web"


class SkillPromptExtension(ComfyExtension):
    async def get_node_list(self):
        return [SkillPromptGenerator, SkillVideoPromptGenerator, SkillLLMServiceConnector]


async def comfy_entrypoint():
    # Defer this import: the server loads custom nodes while initializing itself.
    from server import PromptServer

    register_routes(PromptServer.instance.routes)
    return SkillPromptExtension()
