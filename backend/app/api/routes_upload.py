from fastapi import APIRouter, Depends, UploadFile

from app.core.security import get_current_session_id
from app.core.session_manager import session_manager
from app.graph.knowledge_graph import build_graph_from_documents
from app.ingestion.pipeline import ingest_files
from app.models.schemas import UploadResponse
from app.retrieval.dense import add_to_dense_index, build_dense_index
from app.retrieval.sparse import build_sparse_index

router = APIRouter(prefix="/api", tags=["ingestion"])


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    files: list[UploadFile],
    session_id: str = Depends(get_current_session_id),
) -> UploadResponse:
    session = session_manager.get_session(session_id)

    raw_files = [(f.filename or "unnamed", await f.read()) for f in files]

    async with session.lock:
        result = ingest_files(raw_files)

        if result.chunks:
            if session.vectorstore is None:
                session.vectorstore = build_dense_index(result.chunks)
            else:
                add_to_dense_index(session.vectorstore, result.chunks)

            session.documents.extend(result.chunks)
            session.bm25_retriever = build_sparse_index(session.documents)
            session.uploaded_files.extend(result.files_ingested)

        graph_nodes_created = build_graph_from_documents(result.chunks, tenant_id=session.tenant_id)

    return UploadResponse(
        session_id=session_id,
        files_ingested=result.files_ingested,
        chunks_created=len(result.chunks),
        graph_nodes_created=graph_nodes_created,
        ocr_images_processed=result.ocr_images_processed,
        warnings=result.warnings,
    )
