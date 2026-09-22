import logging
from pathlib import Path

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import GenerationOptions

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent / "configs"
_REFUSAL_MESSAGE = "I'm sorry, I can't respond to that."

_rails: LLMRails | None = None


def get_rails() -> LLMRails:
    global _rails
    if _rails is None:
        config = RailsConfig.from_path(str(_CONFIG_DIR))
        _rails = LLMRails(config)
    return _rails


async def check_input(user_message: str) -> tuple[bool, str | None]:
    """Runs the NeMo Guardrails input rail (jailbreak / prompt-injection / unsafe-content
    self-check) in isolation, without engaging NeMo's own dialog manager. When the rail
    is satisfied, generate_async echoes the input back unchanged; a block replaces it with
    the configured refusal message."""
    try:
        rails = get_rails()
        response = await rails.generate_async(
            messages=[{"role": "user", "content": user_message}],
            options=GenerationOptions(rails=["input"]),
        )
        content = response.response[0]["content"] if response.response else user_message
        if content.strip() == user_message.strip():
            return True, None
        return False, "Prompt injection or unsafe input detected by the input guardrail."
    except Exception:  # noqa: BLE001
        logger.warning("Input guardrail check failed open (allowing input)", exc_info=True)
        return True, None
