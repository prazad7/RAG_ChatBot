import logging

from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_graph_store: Neo4jGraph | None = None
_transformer: LLMGraphTransformer | None = None
_graph_unavailable = False


def is_graph_available() -> bool:
    global _graph_unavailable
    settings = get_settings()
    if not settings.graph_search_enabled:
        return False
    if _graph_unavailable:
        return False
    try:
        get_graph_store()
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Neo4j graph store unreachable; graph search disabled for this process", exc_info=True)
        _graph_unavailable = True
        return False


def get_graph_store() -> Neo4jGraph:
    global _graph_store
    if _graph_store is None:
        settings = get_settings()
        _graph_store = Neo4jGraph(
            url=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
            refresh_schema=False,
        )
        _graph_store.query("RETURN 1")
    return _graph_store


def _get_transformer() -> LLMGraphTransformer:
    global _transformer
    if _transformer is None:
        settings = get_settings()
        llm = ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0)
        _transformer = LLMGraphTransformer(llm=llm)
    return _transformer


def build_graph_from_documents(documents: list[Document], tenant_id: str) -> int:
    """Extracts an entity-relationship graph from the given chunks via LLMGraphTransformer
    and writes it to Neo4j, tagging every node/relationship with tenant_id for strict
    multi-tenant isolation (queries always filter on this property)."""
    if not is_graph_available() or not documents:
        return 0

    transformer = _get_transformer()
    graph_documents = transformer.convert_to_graph_documents(documents)

    node_count = 0
    for graph_doc in graph_documents:
        for node in graph_doc.nodes:
            node.properties["tenant_id"] = tenant_id
            node_count += 1
        for rel in graph_doc.relationships:
            rel.properties["tenant_id"] = tenant_id

    store = get_graph_store()
    store.add_graph_documents(graph_documents, baseEntityLabel=True, include_source=True)
    return node_count


def graph_search(tenant_id: str, key_entities: list[str], limit: int = 10) -> tuple[list[Document], dict]:
    """Looks up key entities in the tenant's slice of the graph and returns 1-hop context
    both as pseudo-documents (for RRF fusion) and as a nodes/edges structure (for the UI)."""
    if not is_graph_available() or not key_entities:
        return [], {"nodes": [], "edges": []}

    store = get_graph_store()
    cypher = """
    UNWIND $entities AS entity
    MATCH (n {tenant_id: $tenant_id})
    WHERE toLower(n.id) CONTAINS toLower(entity)
    OPTIONAL MATCH (n)-[r]-(m {tenant_id: $tenant_id})
    RETURN DISTINCT n.id AS source_id, labels(n) AS source_labels,
           type(r) AS rel_type, m.id AS target_id, labels(m) AS target_labels
    LIMIT $limit
    """
    try:
        records = store.query(cypher, params={"entities": key_entities, "tenant_id": tenant_id, "limit": limit})
    except Exception:  # noqa: BLE001
        logger.warning("Graph search query failed", exc_info=True)
        return [], {"nodes": [], "edges": []}

    documents: list[Document] = []
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    for record in records:
        source_id = record.get("source_id")
        if not source_id:
            continue
        nodes.setdefault(source_id, {"id": source_id, "labels": record.get("source_labels") or []})

        target_id = record.get("target_id")
        rel_type = record.get("rel_type")
        if target_id and rel_type:
            nodes.setdefault(target_id, {"id": target_id, "labels": record.get("target_labels") or []})
            edges.append({"source": source_id, "target": target_id, "relation": rel_type})
            documents.append(
                Document(
                    page_content=f"{source_id} -[{rel_type}]-> {target_id}",
                    metadata={"source": "knowledge_graph", "type": "graph_triple"},
                )
            )
        else:
            documents.append(
                Document(page_content=f"Entity: {source_id}", metadata={"source": "knowledge_graph", "type": "graph_entity"})
            )

    graph_context = {"nodes": list(nodes.values()), "edges": edges}
    return documents, graph_context
