#!/usr/bin/env python3
"""
Neon PostgreSQL setup for Marcela.

End-to-end:
  1. Enable pgvector
  2. Create the conversations table (persistent memory)
  3. Create the knowledge_base table with both `embedding vector(3072)`
     and a GENERATED `embedding_half halfvec(3072)` column
  4. Build the HNSW index on embedding_half (HNSW caps at 2000 dims for
     vector but supports 4000 for halfvec)
  5. Embed every chunk in kb_chunks.json via Gemini gemini-embedding-001
     and insert it. embedding_half is computed by the generated column.

Required env vars:
  DATABASE_URL    Neon connection string
  GEMINI_API_KEY  Google AI key

Optional env vars:
  KB_CHUNKS_FILE  Path to chunks JSON (default: alongside this script)
  KB_CLEAR        "1" to DELETE existing rows before ingest (default: 0)
"""

import json
import os
import sys
import time

import psycopg2
import requests as http_requests

DATABASE_URL = os.environ["DATABASE_URL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072

CHUNKS_FILE = os.environ.get(
    "KB_CHUNKS_FILE",
    os.path.join(os.path.dirname(__file__), "kb_chunks.json"),
)
KB_CLEAR = os.environ.get("KB_CLEAR", "0") == "1"

# Pooler drops the connection on large transactions; insert one row at
# a time and reconnect periodically to avoid SSL EOF errors.
RECONNECT_EVERY = 10


SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

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

CREATE TABLE IF NOT EXISTS knowledge_base (
    id             BIGSERIAL PRIMARY KEY,
    source         TEXT NOT NULL,
    chunk_index    INTEGER NOT NULL,
    content        TEXT NOT NULL,
    embedding      vector({EMBED_DIM}),
    embedding_half halfvec({EMBED_DIM})
                   GENERATED ALWAYS AS (embedding::halfvec({EMBED_DIM})) STORED,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, chunk_index)
);

CREATE INDEX IF NOT EXISTS knowledge_base_embedding_half_hnsw
    ON knowledge_base
    USING hnsw (embedding_half halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""


def connect():
    return psycopg2.connect(DATABASE_URL)


def get_embedding(text: str) -> list[float]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{EMBED_MODEL}:embedContent?key={GEMINI_API_KEY}"
    )
    resp = http_requests.post(
        url,
        json={
            "model": f"models/{EMBED_MODEL}",
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_DOCUMENT",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def setup_schema(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()
    print("✓ Schema ready (pgvector, conversations, knowledge_base, halfvec HNSW)")


def clear_kb(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge_base")
    conn.commit()
    print("✓ Cleared knowledge_base")


def ingest_chunks(conn, chunks: list[dict]):
    total = len(chunks)
    inserted = 0
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        source = chunk["source"]
        idx = chunk["chunk_index"]

        try:
            embedding = get_embedding(text)
        except Exception as e:
            print(f"  [{i+1}/{total}] embedding failed for {source}#{idx}: {e}")
            continue

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO knowledge_base (source, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s::vector({EMBED_DIM}))
                    ON CONFLICT (source, chunk_index) DO UPDATE
                        SET content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding
                    """,
                    (source, idx, text, embedding),
                )
            conn.commit()
            inserted += 1
            print(f"  [{i+1}/{total}] {source}#{idx} ✓")
        except Exception as e:
            print(f"  [{i+1}/{total}] insert failed for {source}#{idx}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

        # Reconnect periodically to keep the pooler happy
        if (i + 1) % RECONNECT_EVERY == 0:
            try:
                conn.close()
            except Exception:
                pass
            conn = connect()
            time.sleep(0.2)

    print(f"\n✓ Inserted {inserted}/{total} chunks")
    return conn


def verify(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM knowledge_base")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT source, COUNT(*) FROM knowledge_base "
            "GROUP BY source ORDER BY source"
        )
        rows = cur.fetchall()
    print(f"\nKB row count: {total}")
    for source, n in rows:
        print(f"  {source}: {n}")


def main():
    print(f"Connecting to Neon at {DATABASE_URL.split('@')[-1].split('/')[0]}…")
    conn = connect()
    print("✓ Connected")

    print("\n1. Schema")
    setup_schema(conn)

    if KB_CLEAR:
        print("\n2. Clearing KB (KB_CLEAR=1)")
        clear_kb(conn)

    print(f"\n3. Loading chunks from {CHUNKS_FILE}")
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"   {len(chunks)} chunks")

    print("\n4. Embedding + ingest")
    conn = ingest_chunks(conn, chunks)

    print("\n5. Verifying")
    verify(conn)

    conn.close()
    print("\n✓ Done")


if __name__ == "__main__":
    sys.exit(main())
