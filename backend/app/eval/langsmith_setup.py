import os

from app.core.config import get_settings


def configure_langsmith() -> None:
    """LangChain/LangSmith read tracing config from environment variables, so full request
    tracing (retrieval, fusion, guardrails, generation) is enabled just by setting these
    before any LangChain component is instantiated."""
    settings = get_settings()
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
