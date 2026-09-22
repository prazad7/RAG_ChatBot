import logging
import os

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_scores_by_turn: dict[str, dict] = {}


def ensure_deepeval_env() -> None:
    settings = get_settings()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.confident_api_key:
        os.environ.setdefault("CONFIDENT_API_KEY", settings.confident_api_key)


def compute_eval_scores(turn_id: str, question: str, answer: str, context_chunks: list[str]) -> None:
    """Runs DeepEval's AnswerRelevancy and Faithfulness metrics (each an LLM-judge call)
    for observability. Intentionally synchronous/blocking internally — callers run this
    inside a FastAPI BackgroundTask so it never delays the chat response itself."""
    settings = get_settings()
    if not settings.deepeval_enabled or not settings.openai_api_key:
        _scores_by_turn[turn_id] = {"status": "disabled"}
        return

    ensure_deepeval_env()
    try:
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
        from deepeval.test_case import LLMTestCase

        test_case = LLMTestCase(
            input=question,
            actual_output=answer,
            retrieval_context=context_chunks or [""],
        )
        relevancy_metric = AnswerRelevancyMetric(threshold=0.5, include_reason=False)
        faithfulness_metric = FaithfulnessMetric(threshold=0.5, include_reason=False)

        relevancy_metric.measure(test_case)
        faithfulness_metric.measure(test_case)

        _scores_by_turn[turn_id] = {
            "status": "completed",
            "answer_relevancy": relevancy_metric.score,
            "faithfulness": faithfulness_metric.score,
        }
    except Exception:  # noqa: BLE001
        logger.warning("DeepEval scoring failed for turn %s", turn_id, exc_info=True)
        _scores_by_turn[turn_id] = {"status": "failed"}


def get_eval_scores(turn_id: str) -> dict | None:
    return _scores_by_turn.get(turn_id)
