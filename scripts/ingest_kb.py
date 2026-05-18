#!/usr/bin/env python3
"""
Fast KB ingestion: embed all chunks and insert into Neon pgvector.
Uses gemini-embedding-001 (3072 dims) and psycopg2 direct connection.
"""

import json, os, sys, time
import psycopg2
from psycopg2.extras import execute_values
import requests

DB_URL = os.environ["DATABASE_URL"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072
CHUNKS_FILE = os.environ.get(
    "KB_CHUNKS_FILE",
    os.path.join(os.path.dirname(__file__), "kb_chunks.json"),
)

EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent?key={GEMINI_KEY}"

def embed(text):
    r = requests.post(EMBED_URL, json={
        "model": f"models/{EMBED_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_DOCUMENT"
    }, timeout=20)
    r.raise_for_status()
    return r.json()["embedding"]["values"]

def main():
    print("Connecting to Neon...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("Setting up schema...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id BIGSERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding VECTOR({EMBED_DIM}),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(source, chunk_index)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id BIGSERIAL PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user','assistant')),
            content TEXT NOT NULL,
            platform TEXT NOT NULL DEFAULT 'whatsapp',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS conv_id_idx ON conversations (conversation_id, created_at DESC)")
    cur.execute("DELETE FROM knowledge_base")
    conn.commit()
    print("Schema ready, KB cleared.")

    chunks = json.load(open(CHUNKS_FILE))
    print(f"Embedding {len(chunks)} chunks...")

    rows = []
    for i, c in enumerate(chunks):
        try:
            vec = embed(c["text"])
            rows.append((c["source"], c["chunk_index"], c["text"], vec))
            print(f"  [{i+1}/{len(chunks)}] {c['source']} chunk {c['chunk_index']} ✓")
        except Exception as e:
            print(f"  [{i+1}/{len(chunks)}] ERROR: {e}")
        if (i+1) % 15 == 0:
            time.sleep(0.3)

    print(f"\nInserting {len(rows)} rows into Neon (batched)...")
    BATCH = 10
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start+BATCH]
        # Reconnect for each batch to avoid pooler SSL timeout
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        execute_values(
            cur,
            "INSERT INTO knowledge_base (source, chunk_index, content, embedding) VALUES %s "
            "ON CONFLICT (source, chunk_index) DO UPDATE SET content=EXCLUDED.content, embedding=EXCLUDED.embedding",
            batch,
            template="(%s, %s, %s, %s::vector)"
        )
        conn.commit()
        print(f"  Inserted rows {start+1}-{min(start+BATCH, len(rows))} of {len(rows)}")
        time.sleep(0.2)

    # Create IVFFlat index (HNSW max 2000 dims; IVFFlat supports 3072)
    print("Creating IVFFlat index...")
    conn2 = psycopg2.connect(DB_URL)
    cur2 = conn2.cursor()
    cur2.execute("DROP INDEX IF EXISTS kb_ivfflat_idx")
    cur2.execute("CREATE INDEX kb_ivfflat_idx ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists=50)")
    conn2.commit()
    conn2.close()

    # Verify
    cur.execute("SELECT source, COUNT(*) FROM knowledge_base GROUP BY source ORDER BY source")
    rows_check = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM knowledge_base")
    total = cur.fetchone()[0]
    print(f"\n✓ Total rows: {total}")
    for src, n in rows_check:
        print(f"   {src}: {n}")

    conn.close()
    print("\n✓ Done!")

if __name__ == "__main__":
    main()
