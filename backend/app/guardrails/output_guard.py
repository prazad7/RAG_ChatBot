import logging

from nemoguardrails.rails.llm.options import GenerationOptions

from app.guardrails.input_guard import get_rails

logger = logging.getLogger(__name__)


async def check_output_safety(answer: str) -> bool:
    """NeMo Guardrails self-check on the generated answer for generic safety concerns."""
    try:
        rails = get_rails()
        response = await rails.generate_async(
            messages=[{"role": "user", "content": "n/a"}, {"role": "assistant", "content": answer}],
            options=GenerationOptions(rails=["output"]),
        )
        content = response.response[0]["content"] if response.response else answer
        return content.strip() == answer.strip()
    except Exception:  # noqa: BLE001
        logger.warning("Output safety guardrail check failed open (allowing output)", exc_info=True)
        return True
