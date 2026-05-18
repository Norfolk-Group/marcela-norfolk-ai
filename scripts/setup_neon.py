#!/usr/bin/env python3
"""
Neon PostgreSQL setup for Marcela:
1. Enable pgvector extension
2. Create knowledge_base table (RAG chunks + embeddings)
3. Create conversations table (persistent memory)
4. Embed all KB chunks via Gemini text-embedding-004
5. Ingest into pgvector with HNSW index
"""

import json
import os
import sys
import time
import psycopg2
from psycopg2.extras import execute_values

# ── Config ───────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ["DATABASE_URL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072  # gemini-embedding-001 outputs 3072 dimensions
CHUNKS_FILE = os.environ.get(
    "KB_CHUNKS_FILE",
    os.path.join(os.path.dirname(__file__), "kb_chunks.json"),
)

# ── Gemini Embedding ─────────────────────────────────────────────────────────

import requests as http_requests

def get_embedding(text: str) -> list[float]:
    """Get embedding from Gemini text-embedding-004."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"
    payload = {
        "model": f"models/{EMBED_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_DOCUMENT",
    }
    resp = http_requests.post(
        f"{url}?key={GEMINI_API_KEY}",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "embedding" not in data:
        raise ValueError(f"No embedding in response: {data}")
    return data["embedding"]["values"]


def get_query_embedding(text: str) -> list[float]:
    """Get embedding for a query (different task type for better retrieval)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"
    payload = {
        "model": f"models/{EMBED_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_QUERY",
    }
    resp = http_requests.post(
        f"{url}?key={GEMINI_API_KEY}",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


# ── Database Setup ───────────────────────────────────────────────────────────

SCHEMA_SQL = f"""
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Knowledge base: Norfolk AI document chunks with embeddings
CREATE TABLE IF NOT EXISTS knowledge_base (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    embedding   VECTOR({EMBED_DIM}),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, chunk_index)
);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS knowledge_base_embedding_hnsw
    ON knowledge_base
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Persistent conversation memory (cross-session)
CREATE TABLE IF NOT EXISTS conversations (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    platform        TEXT NOT NULL DEFAULT 'whatsapp',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS conversations_conv_id_idx
    ON conversations (conversation_id, created_at DESC);
"""


def setup_schema(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()
    print("✓ Schema created (pgvector, knowledge_base, conversations)")


def clear_kb(conn):
    """Clear existing KB entries so we can re-ingest cleanly."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge_base")
    conn.commit()
    print("✓ Cleared existing knowledge_base rows")


def ingest_chunks(conn, chunks: list[dict]):
    """Embed and insert all chunks into knowledge_base."""
    rows = []
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        source = chunk["source"]
        idx = chunk["chunk_index"]

        print(f"  [{i+1}/{total}] Embedding: {source} chunk {idx} ({len(text)} chars)")

        try:
            embedding = get_embedding(text)
        except Exception as e:
            print(f"    ✗ Embedding failed: {e} — skipping")
            continue

        rows.append((source, idx, text, embedding))

        # Rate limit: Gemini free tier ~1500 RPM, be safe
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    if not rows:
        print("No rows to insert!")
        return

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO knowledge_base (source, chunk_index, content, embedding)
            VALUES %s
            ON CONFLICT (source, chunk_index) DO UPDATE
                SET content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding
            """,
            [(r[0], r[1], r[2], r[3]) for r in rows],
            template="(%s, %s, %s, %s::vector)",
        )
    conn.commit()
    print(f"\n✓ Ingested {len(rows)} chunks into knowledge_base")


def verify(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM knowledge_base")
        count = cur.fetchone()[0]
        cur.execute("SELECT source, COUNT(*) FROM knowledge_base GROUP BY source ORDER BY source")
        rows = cur.fetchall()
    print(f"\n✓ Verification — total rows: {count}")
    for source, n in rows:
        print(f"   {source}: {n} chunks")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    print(f"Connecting to Neon...")
    conn = psycopg2.connect(DATABASE_URL)
    print("✓ Connected")

    print("\n1. Setting up schema...")
    setup_schema(conn)

    print("\n2. Loading chunks...")
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"   Loaded {len(chunks)} chunks from {CHUNKS_FILE}")

    print("\n3. Clearing existing KB...")
    clear_kb(conn)

    print("\n4. Embedding and ingesting chunks...")
    ingest_chunks(conn, chunks)

    print("\n5. Verifying...")
    verify(conn)

    conn.close()
    print("\n✓ Done! Neon pgvector KB is ready.")


if __name__ == "__main__":
    main()
