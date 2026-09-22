from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    session_token: str
    session_id: str
    expires_at: str


class UploadResponse(BaseModel):
    session_id: str
    files_ingested: list[str]
    chunks_created: int
    graph_nodes_created: int
    ocr_images_processed: int
    warnings: list[str] = Field(default_factory=list)


class ConfigUpdateRequest(BaseModel):
    use_dense: bool | None = None
    use_sparse: bool | None = None
    use_graph: bool | None = None
    use_rerank: bool | None = None
    top_k: int | None = None


class ChatRequest(BaseModel):
    message: str


class SourceAttribution(BaseModel):
    file_name: str
    chunk_index: int
    preview: str
    retriever: str
    score: float


class GraphContext(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class GuardrailInfo(BaseModel):
    input_allowed: bool
    input_reason: str | None = None
    output_grounded: bool
    grounding_score: float
    rewritten_query: str


class ChatResponse(BaseModel):
    turn_id: str
    answer: str
    sources: list[SourceAttribution]
    graph_context: GraphContext
    elapsed_seconds: float
    guardrail: GuardrailInfo


class EvalScores(BaseModel):
    turn_id: str
    answer_relevancy: float | None = None
    faithfulness: float | None = None
    status: str
