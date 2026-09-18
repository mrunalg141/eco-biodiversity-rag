import os
import time
import chromadb
from pypdf import PdfReader
from fastembed import TextEmbedding

os.environ["OMP_NUM_THREADS"] = str(os.cpu_count())

KNOWLEDGE_BASE_DIR = "knowledge_base"
CATEGORIES = ["soil", "land_use", "biodiversity", "climate", "human_impact"]

embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("env_knowledge_base")


def extract_pdf_text(path):
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text, chunk_size=400, overlap=60):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + chunk_size]))
        i += chunk_size - overlap
    return chunks


def build_index():
    total_chunks = 0

    for category in CATEGORIES:
        folder = os.path.join(KNOWLEDGE_BASE_DIR, category)
        if not os.path.isdir(folder):
            print(f"SKIP - no folder found for category '{category}'")
            continue

        for filename in os.listdir(folder):
            if not filename.lower().endswith(".pdf"):
                continue

            path = os.path.join(folder, filename)
            print(f"Indexing [{category}] {filename}...")

            start = time.time()
            text = extract_pdf_text(path)
            chunks = chunk_text(text)

            if not chunks:
                print(f"  WARNING - no extractable text in {filename}")
                continue

            embeddings = [e.tolist() for e in embedder.embed(chunks)]

            collection.add(
                ids=[f"{category}_{filename}_{i}" for i in range(len(chunks))],
                embeddings=embeddings,
                documents=chunks,
                metadatas=[{"category": category, "source": filename} for _ in chunks]
            )

            total_chunks += len(chunks)
            print(f"  Done - {len(chunks)} chunks in {time.time() - start:.2f}s")

    print(f"\nKnowledge base built: {total_chunks} total chunks across {len(CATEGORIES)} categories")


if __name__ == "__main__":
    build_index()