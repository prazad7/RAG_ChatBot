from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingestion.loaders import load_file

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)


@dataclass
class IngestionResult:
    chunks: list[Document] = field(default_factory=list)
    files_ingested: list[str] = field(default_factory=list)
    ocr_images_processed: int = 0
    warnings: list[str] = field(default_factory=list)


def ingest_files(files: list[tuple[str, bytes]]) -> IngestionResult:
    result = IngestionResult()

    for file_name, content in files:
        load_result = load_file(file_name, content)
        result.warnings.extend(load_result.warnings)
        result.ocr_images_processed += load_result.ocr_images_processed

        if not load_result.documents:
            continue

        result.files_ingested.append(file_name)
        split_docs = _splitter.split_documents(load_result.documents)
        for idx, doc in enumerate(split_docs):
            doc.metadata["chunk_index"] = idx
            doc.metadata.setdefault("source", file_name)
        result.chunks.extend(split_docs)

    return result
