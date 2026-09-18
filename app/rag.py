import time
import chromadb
from pypdf import PdfReader
from fastembed import TextEmbedding

from script.knowledgebase import extract_pdf_text

embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", providers=["CPUExecutionProvider"])

print("DEBUG - warming up embedder...")
_warmup_start = time.time()
dummy_chunks = ["This is a sample sentence used only to warm up the embedding model."] * 10
list(embedder.embed(dummy_chunks))
print(f"DEBUG - embedder warmup took {time.time() - _warmup_start:.2f}s")

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("studymate_docs")
env_collection = chroma_client.get_or_create_collection("env_knowledge_base")


# ---------------------------------------------------------------------------
# Original StudyMate functions (user-uploaded notes -> "studymate_docs")
# ---------------------------------------------------------------------------

def chunk_text(text, chunk_size=250, overlap=20):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i+chunk_size]))
        i += chunk_size - overlap
    return chunks


def index_pdf(path, doc_id):
    start = time.time()
    text = extract_pdf_text(path)
    print(f"DEBUG - extraction took {time.time() - start:.2f}s")

    t2 = time.time()
    chunks = chunk_text(text)
    print(f"DEBUG - created {len(chunks)} chunks in {time.time() - t2:.2f}s")

    t3 = time.time()
    embeddings = [e.tolist() for e in embedder.embed(chunks)]
    print(f"DEBUG - embedding took {time.time() - t3:.2f}s")

    t4 = time.time()
    collection.add(
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=chunks,
        metadatas=[{"doc_id": doc_id} for _ in chunks]
    )
    print(f"DEBUG - chroma add took {time.time() - t4:.2f}s")
    return len(chunks)


def retrieve_context(question, top_k=3, threshold=1.8):
    q_embedding = list(embedder.embed([question]))[0].tolist()
    results = collection.query(query_embeddings=[q_embedding], n_results=top_k)
    print("DEBUG - documents found:", len(results["documents"][0]))
    print("DEBUG - distances:", results["distances"][0])
    if not results["documents"][0]:
        return ""
    distances = results["distances"][0]
    if min(distances) > threshold:
        print(f"DEBUG - REJECTED: min distance {min(distances)} > threshold {threshold}")
        return ""
    return "\n\n".join(results["documents"][0])


def clear_collection():
    global collection
    chroma_client.delete_collection("studymate_docs")
    collection = chroma_client.get_or_create_collection("studymate_docs")


# ---------------------------------------------------------------------------
# New: fixed environmental knowledge base -> "env_knowledge_base"
# ---------------------------------------------------------------------------

def index_env_pdf(path, doc_id, category):
    """Same as index_pdf(), but tags each chunk with a category and writes
    to the separate env_knowledge_base collection instead of studymate_docs."""
    start = time.time()
    text = extract_pdf_text(path)
    print(f"DEBUG - extraction took {time.time() - start:.2f}s")

    t2 = time.time()
    chunks = chunk_text(text)
    print(f"DEBUG - created {len(chunks)} chunks in {time.time() - t2:.2f}s")

    t3 = time.time()
    embeddings = [e.tolist() for e in embedder.embed(chunks)]
    print(f"DEBUG - embedding took {time.time() - t3:.2f}s")

    t4 = time.time()
    env_collection.add(
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=chunks,
        metadatas=[{"doc_id": doc_id, "source": doc_id, "category": category} for _ in chunks]
    )
    print(f"DEBUG - chroma add took {time.time() - t4:.2f}s")
    return len(chunks)


def build_env_knowledge_base():
    """Fixed pre-indexed set — run once (see app/main.py startup snippet)."""
    sources = [
        ("docs/fao_recarbonizing_global_soils.pdf", "FAO-Recarbonizing-Soils-2021", "soil"),
        ("docs/fao_soc_hidden_potential.pdf", "FAO-SOC-Hidden-Potential-2017", "soil"),
        ("docs/ipcc_srccl_spm.pdf", "IPCC-SRCCL-SPM-2019", "climate"),
        ("docs/ipbes_global_assessment_spm.pdf", "IPBES-Global-Assessment-SPM-2019", "biodiversity"),
        ("docs/global_land_outlook.pdf", "UNCCD-Global-Land-Outlook-2017", "land_use"),
        ("docs/fao_sofa_2025.pdf", "FAO-SOFA-2025", "human_impact"),
    ]
    for path, doc_id, category in sources:
        print(f"DEBUG - indexing {doc_id} ({category})")
        index_env_pdf(path, doc_id, category)


def retrieve_context_by_category(question, category, top_k=3, threshold=1.8):
    """Same pattern as retrieve_context(), scoped to one category. Call once
    per category (soil, climate, biodiversity, land_use, human_impact) for
    multi-metric reasoning, rather than one flat query across everything."""
    q_embedding = list(embedder.embed([question]))[0].tolist()
    results = env_collection.query(
        query_embeddings=[q_embedding],
        n_results=top_k,
        where={"category": category},
    )
    docs = results["documents"][0]
    distances = results["distances"][0]
    print(f"DEBUG [{category}] - documents found:", len(docs))
    print(f"DEBUG [{category}] - distances:", distances)

    if not docs:
        return [], []
    if min(distances) > threshold:
        print(f"DEBUG [{category}] - REJECTED: min distance {min(distances)} > threshold {threshold}")
        return [], []

    metas = results["metadatas"][0]
    return docs, metas