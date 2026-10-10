"""Vector search over the policy documents.

The store is behind a tiny interface on purpose: swapping Chroma for a Bedrock
Knowledge Base later means writing one more class, not touching the agents.
"""
import re
from pathlib import Path
from config import POLICY_DIR, CHROMA_DIR, EMBEDDINGS, AWS_REGION, TITAN_MODEL_ID

COLLECTION = "policies"


def _chunks(path: Path):
    """Split a policy doc on its section headings, keeping metadata with each chunk."""
    raw = path.read_text()
    meta = {}
    if raw.startswith("---"):
        front, raw = raw.split("---", 2)[1:]
        for line in front.strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    parts = re.split(r"\n(?=## )", raw)
    out = []
    for part in parts:
        text = part.strip()
        if len(text) < 40:
            continue
        heading = text.splitlines()[0].lstrip("# ").strip()
        out.append({
            "text": text,
            "metadata": {
                "doc_id": meta.get("doc_id", path.stem),
                "title": meta.get("title", path.stem),
                "section": heading,
                "effective": meta.get("effective", ""),
                "status": meta.get("status", "current"),
                "source": f"{meta.get('doc_id', path.stem)} {heading}",
            },
        })
    return out


def _embedding_fn():
    if EMBEDDINGS == "titan":
        from chromadb.utils.embedding_functions import AmazonBedrockEmbeddingFunction
        import boto3
        session = boto3.Session(region_name=AWS_REGION)
        return AmazonBedrockEmbeddingFunction(session=session, model_name=TITAN_MODEL_ID)
    return None          # Chroma's built-in local model, no AWS needed


def _collection(reset=False):
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if reset:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
    kwargs = {"name": COLLECTION}
    fn = _embedding_fn()
    if fn:
        kwargs["embedding_function"] = fn
    return client.get_or_create_collection(**kwargs)


def ingest():
    """Build the index from policies/. Safe to re-run."""
    col = _collection(reset=True)
    ids, docs, metas = [], [], []
    for path in sorted(POLICY_DIR.glob("*.md")):
        for i, ch in enumerate(_chunks(path)):
            ids.append(f"{path.stem}-{i}")
            docs.append(ch["text"])
            metas.append(ch["metadata"])
    col.add(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def search(query: str, k: int = 4, current_only: bool = True):
    """Return [{text, source, section, doc_id}] most relevant to the query."""
    col = _collection()
    where = {"status": "current"} if current_only else None
    res = col.query(query_texts=[query], n_results=k, where=where)
    hits = []
    for text, meta in zip(res["documents"][0], res["metadatas"][0]):
        hits.append({"text": text, "source": meta["source"],
                     "section": meta["section"], "doc_id": meta["doc_id"]})
    return hits


if __name__ == "__main__":
    print(f"indexed {ingest()} policy chunks")
    for h in search("how long do we have to investigate an unauthorized charge"):
        print(" -", h["source"])
