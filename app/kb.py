"""
Knowledge base: loads official sections, splits long ones into chunks, and
builds/loads a hybrid search index (BM25 keywords + multilingual embeddings).

Citations always point at a *section* (`id`), never at a chunk, so the
citation checker can verify them against the official data.
"""

import json
import pickle
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SECTIONS_PATH = ROOT / "data" / "processed" / "sections.jsonl"
INDEX_DIR = ROOT / "data" / "index"

# Multilingual so Hindi/Hinglish questions can match English law text.
# ~470 MB, runs on CPU. Swap for a bigger model (e.g. BAAI/bge-m3) if you have the RAM.
EMBED_MODEL = "intfloat/multilingual-e5-small"

CHUNK_CHARS = 1500
CHUNK_OVERLAP = 200


def load_sections():
    sections = {}
    with SECTIONS_PATH.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            # Skip sections that have been omitted/repealed by amendment.
            if r["heading"].strip().lower().startswith(("omitted", "repealed")) or len(r["text"]) < 20:
                continue
            sections[r["id"]] = r
    return sections


def clean_for_display(text):
    """Remove amendment footnote markers like '1 [' and ']' left in India Code text."""
    text = re.sub(r"\b\d+\s*\[", "", text)
    return text.replace("]", "")


def make_chunks(sections):
    chunks = []
    for sid, s in sections.items():
        text = clean_for_display(s["text"])
        start, part = 0, 0
        while True:
            piece = text[start:start + CHUNK_CHARS]
            chunks.append({
                "chunk_id": f"{sid}#{part}",
                "section_id": sid,
                "act": s["act"],
                "section": s["section"],
                "heading": s["heading"],
                "text": piece,
            })
            if start + CHUNK_CHARS >= len(text):
                break
            start += CHUNK_CHARS - CHUNK_OVERLAP
            part += 1
    return chunks


def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_doc(c):
    # Headings are the best summary of a section, so weight them up.
    return tokenize(f"{c['heading']} {c['heading']} {c['heading']} {c['act']} {c['text']}")


def embed_doc(c):
    return f"passage: {c['act']}, Section {c['section']}: {c['heading']}. {c['text']}"


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


def build_index():
    from rank_bm25 import BM25Okapi

    sections = load_sections()
    chunks = make_chunks(sections)
    print(f"{len(sections)} sections -> {len(chunks)} chunks")

    bm25 = BM25Okapi([bm25_doc(c) for c in chunks])
    print("Embedding chunks (first run downloads the model)...")
    vecs = get_embedder().encode(
        [embed_doc(c) for c in chunks], batch_size=32, show_progress_bar=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with (INDEX_DIR / "chunks.pkl").open("wb") as f:
        pickle.dump({"chunks": chunks, "bm25": bm25, "model": EMBED_MODEL}, f)
    np.save(INDEX_DIR / "embeddings.npy", vecs)
    print(f"Index saved to {INDEX_DIR}")


@lru_cache(maxsize=1)
def load_index():
    path = INDEX_DIR / "chunks.pkl"
    if not path.exists():
        raise FileNotFoundError("No index found. Run: python scripts/build_index.py")
    with path.open("rb") as f:
        data = pickle.load(f)
    data["embeddings"] = np.load(INDEX_DIR / "embeddings.npy")
    data["sections"] = load_sections()
    return data
