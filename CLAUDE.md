# Marcela — Norfolk AI AI Agent

## Project Overview

Marcela is Ricardo Cidale's personal AI assistant, built for Norfolk AI. She operates across two channels: **voice calls** (inbound phone) and **WhatsApp messaging**. The project has gone through multiple architectural iterations, platform migrations, and debugging cycles documented below.

**Owner**: Ricardo Cidale, Founder & CEO of Norfolk AI (Austin, TX)
**Repository**: `Norfolk-Group/marcela-norfolk-ai` (private)

---

## Architecture Summary

| Component | Technology | Deployment |
|---|---|---|
| WhatsApp Agent | Flask + Gemini 2.5 Flash (direct HTTP) | Vercel Serverless (`api/index.py`) |
| Voice Agent | Starlette + Gemini 2.5 Flash (streaming) + ConversationRelay | Railway (Docker container) |
| STT | Deepgram nova-3-general | Via Twilio ConversationRelay |
| TTS | ElevenLabs Flash 2.5 | Via Twilio ConversationRelay |
| LLM | Google Gemini 2.5 Flash | Direct API (WhatsApp) / google-genai SDK (Voice) |
| Telephony | Twilio | WhatsApp Messaging + Voice ConversationRelay |

### Phone Numbers

| Number | Purpose | Status |
|---|---|---|
| +15559178507 | Marcela WhatsApp (messaging) | **ACTIVE — Connected, High quality** |
| +19109944861 | Marcela Voice AI (inbound calls) + Norfolk AI Voice Digest | Voice Digest sender is Offline |
| +15126699705 | Ricardo's personal number | Active |

### Deployment URLs

| Service | URL |
|---|---|
| WhatsApp webhook (Vercel) | `https://marcela-norfolk-ai.vercel.app/webhook` |
| Health check (Vercel) | `https://marcela-norfolk-ai.vercel.app/health` |
| Voice server (Railway) | Configured via `PUBLIC_URL` env var |

---

## Critical Issues (Current)

### ~~WhatsApp Error 63112~~ — RESOLVED (May 2, 2026)

**Status**: RESOLVED

Marcela is now fully operational. The root causes were:

1. **Wrong webhook URL**: The WhatsApp sender `+15559178507` had its webhook pointing to `https://passport-tracker-seven.vercel.app/api/whatsapp` (a completely different project). Fixed by updating to `https://marcela-norfolk-ai.vercel.app/webhook` in Twilio console > Messaging > Numbers and Senders > WhatsApp > +15559178507 > Messaging Endpoint Configuration.

2. **Vercel deployment crash (HTTP 500)**: The `requirements.txt` was rewritten for the voice server (Railway) and Flask was removed — but `api/index.py` imports Flask. This caused `FUNCTION_INVOCATION_FAILED` on every request. Fixed by restoring `flask` and `requests` as the only dependencies in `requirements.txt` (Vercel only needs these two).

3. **Stale Twilio auth token**: The hardcoded fallback auth token `ac4b34ff...` in `api/index.py` was rotated/expired. Fixed by removing all hardcoded credential fallbacks and updating `TWILIO_AUTH_TOKEN` in Vercel environment variables.

4. **Vercel-GitHub auto-deploy broken**: The Vercel GitHub App lost access to the Norfolk-Group organization after the repo was transferred. Fixed by adding a GitHub Actions workflow (`.github/workflows/deploy.yml`) that deploys to Vercel via CLI token on every push. **Action required**: Add `VERCEL_TOKEN` as a GitHub secret in the Norfolk-Group/marcela-norfolk-ai repo settings.

**Investigation findings (May 2, 2026)**:
- Meta Business Suite shows WABA (446936301829143) as **Approved** with **Verified** business — Meta was NOT blocking anything
- Phone number `+15559178507` shows **Connected** with **High** quality rating in Meta
- The real issue was the wrong webhook URL, not a Meta/WABA block as previously diagnosed

### Norfolk AI Voice Digest Sender Offline

The second WhatsApp sender `+19109944861` (Norfolk AI Voice Digest) shows **Offline** status in Twilio with **Unknown** quality rating and **Unverified** in Meta. This number is also the voice line. Needs Meta WhatsApp verification.

---

## File Map

| File | Description |
|---|---|
| `api/index.py` | Vercel serverless entry point — Flask app handling WhatsApp, Slack, and Telegram with Neon RAG |
| `voice_server.py` | Voice + WhatsApp Starlette server (Gemini via google-genai SDK, streaming) |
| `create_elevenlabs_agent.py` | Script to create ElevenLabs ConvAI agent via API (historical) |
| `marcela_agent_config.json` | Agent metadata: IDs, phone numbers, capabilities |
| `prompts/marcela-voice-prompt.txt` | Production voice prompt with call screening logic |
| `prompts/marcela-context.txt` | Background context about Ricardo, Norfolk AI, Super Conversations |
| `marcela-profile.png` | Marcela's WhatsApp profile image |
| `BrandguidelineNorfolkAI.pdf` | Norfolk AI brand guidelines |
| `vercel.json` | Vercel deployment config (routes all to `api/index.py`) |
| `Dockerfile` | Container build for Railway deployment |
| `railway.toml` | Railway deployment config |
| `Procfile` | Process declaration for Railway |
| `requirements.txt` | Python dependencies |
| `runtime.txt` | Python runtime version spec |

---

## Complete Project History

### Phase 1: Initial WhatsApp Agent (March 17, 2026)

**Commit**: `b22d315` — Initial commit

- Built Marcela as a WhatsApp AI agent using **Anthropic Claude** as the LLM and **Twilio Python SDK** for messaging
- Used `+15126699705` (Ricardo's personal number) as the WhatsApp sender
- Basic webhook architecture: receive message → call Claude → send response via Twilio API

### Phase 2: Sender Number Changes (March 18, 2026)

**Commits**: `0082827`, `8f457d1`, `9a9a45b`

- Changed sender from Ricardo's personal number to `+19109944861` (the Twilio voice number)
- Added Vercel serverless deployment config (`vercel.json`, `api/index.py`)
- Later changed sender to `+15559178507` (dedicated WhatsApp Business number)

### Phase 3: Group Chat Features (March 18, 2026)

**Commits**: `4a2ab03`, `57cce5b`

- Added `@Marcela` mention-based trigger for group chats (silent unless called)
- Added slash commands: `/ask`, `/quick`, `/translate`
- Added natural mention triggers (regex-based detection)

### Phase 4: Vercel Compatibility Fixes — FAILED ATTEMPTS (March 18, 2026)

**Commits**: `75142cb`, `25a8b17`, `4f90d01`

This was a series of cascading failures caused by Vercel's serverless environment:

1. **Failed**: Twilio Python SDK caused `httpx` version conflict on Vercel. Tried lazy-init clients and pinning twilio version — did not resolve.
2. **Failed**: Tried replacing both Anthropic and Twilio SDKs with direct HTTP requests — partially worked but Anthropic API still had issues.
3. **Resolution**: Switched entirely from Anthropic Claude to **Google Gemini 2.5 Flash** using direct HTTP requests (no SDK). This eliminated all dependency conflicts on Vercel.

**Lesson learned**: Vercel serverless functions have strict dependency constraints. Avoid heavy SDKs (anthropic, twilio) — use direct HTTP requests instead. The Gemini API is lightweight and works well with simple `requests` calls.

### Phase 5: Error 63112 — TwiML Fix Attempt (March 18, 2026)

**Commit**: `7a60a6c` — "fix: respond via inline TwiML instead of Twilio API to avoid error 63112"

- Outbound WhatsApp messages started failing with error 63112
- **Attempted fix**: Changed from sending responses via Twilio REST API (`send_whatsapp_message()`) to returning inline TwiML responses (`message_twiml()`) from the webhook
- **Result**: DID NOT FIX THE ISSUE. Twilio internally converts TwiML responses to API calls, so the same 63112 error occurs. The error is at the Meta/WABA level, not the Twilio API level.

**Lesson learned**: Error 63112 cannot be fixed with code changes. It means Meta has disabled the WhatsApp Business Account. The fix must happen in Meta Business Suite.

### Phase 6: Voice Agent Development (March 19, 2026)

**Commits**: `2b343e0`, `c02a8f0`, `ec8ee8b`, `da0b88e`, `b8e4378`

- Built Marcela Voice AI Agent using Twilio ConversationRelay + Gemini 2.5 Flash streaming
- Architecture: Caller → Twilio → ConversationRelay (Deepgram STT) → WebSocket → Gemini streaming → WebSocket → ConversationRelay (ElevenLabs TTS) → Caller
- Refactored to single-port architecture (HTTP + WebSocket on same port) for Railway compatibility
- Added Dockerfile for container deployment
- Multiple fixes for form parsing, python-multipart dependency, API key auth, and error handling on Railway

**Failed attempts during voice development**:
- Initially tried separate ports for HTTP (5005) and WebSocket (8765) — failed on Railway which only exposes one port
- Form parsing broke on Railway due to missing `python-multipart` package
- Had to add robust try/except with fallback URL-encoded body parsing

### Phase 7: ElevenLabs ConvAI Agent (March 19, 2026)

**Commit**: `fe4f37f`

- Created an ElevenLabs Conversational AI agent as an alternative/complement to the custom voice server
- Agent ID: `agent_5401km3m8hfrer5rmpetb7wefdyt`
- Uses Qwen3-30B-A3B model (chosen for speed — output tokens matter 50x more than prompt size for latency)
- Voice: Jessica Anne Bogart - Chatty
- Includes simulation tests for call screening scenarios

### Phase 8: Documentation (March 19, 2026)

**Commit**: `1d02950`

- Added initial CLAUDE.md with project learnings
- Updated voice prompt and context files

---

## Prompt Engineering Learnings

### Call Screening Architecture

The voice prompt uses a layered screening system: Always Transfer → Transfer if Qualified → Never Transfer → Borderline. The critical discovery was that without an explicit **priority rule** ("one disqualifying signal overrides all qualifying ones"), the LLM would rationalize transfers for borderline callers who mixed qualifying and disqualifying signals.

### Data Collection Discipline

The agent must be explicitly instructed to collect name, title, company, and email EARLY in the conversation. Without timing instructions, the agent gets engaged in the conversation content and forgets administrative tasks. The prompt now includes: "Never end a call without having collected the caller's email."

### Sales Detection

An explicit step ("Is this person selling something?") is required in the screening flow. The LLM will not reliably infer that a "partnership opportunity" or "collaboration" pitch is actually a sales call without being told to check.

### Conference Contacts

Meeting someone at a conference does NOT make them an existing client. This had to be stated explicitly — the LLM would otherwise treat conference encounters as qualifying relationships.

### Test-Driven Prompt Development

The most effective workflow: write prompt → create simulation tests → run → analyze failures → fix prompt → re-run failing tests. Each iteration improved pass rate from 2/4 to 3/4 to 4/4.

---

## Latency Optimization (Voice)

- Output token reduction has approximately 50x more impact on latency than system prompt size
- ElevenLabs has best-in-class latency at sub-500ms (vs VAPI ~500ms, Retell ~800ms, Bland AI ~800-2500ms)
- Turn detection/endpointing is the highest-impact optimization area
- Keep agent responses to 1-2 sentences per turn
- Streaming token delivery at sentence boundaries produces the most natural speech

---

## Integrations

| Integration | Purpose | Status |
|---|---|---|
| HubSpot (via Zapier) | CRM logging after each call | Configured |
| Gmail (via Zapier) | Follow-up emails on Ricardo's behalf | Configured |
| Google Calendar (via Zapier) | Meeting booking | Needs OAuth reconnection (3 accounts) |
| Slack | High-priority notifications to Ricardo | Configured |

---

## Environment Variables

### WhatsApp (Vercel)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID: `AC2354928595411f3e4156a44683af210d` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `WHATSAPP_SENDER` | `whatsapp:+15559178507` |

### Voice (Railway)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_API_KEY` | Twilio API Key (for ConversationRelay) |
| `TWILIO_API_SECRET` | Twilio API Secret |
| `PUBLIC_URL` | Public WSS URL for ConversationRelay |
| `PORT` | Server port (default: 5005) |

---

## Twilio Account Details

| Item | Value |
|---|---|
| Account SID | `AC2354928595411f3e4156a44683af210d` |
| WABA ID | `446936301829143` |
| Messaging Service (Marcela) | `MG5749f41a32f687f44e27d73f4d11baa9` |
| Messaging Service (empty, March 18) | `MG21f0694cd1b2566a13873571d2106728` — created accidentally, has no senders |
| WhatsApp Content Template | `HXf0178fa997208550fc9ea2a64e0b2b91` (norfolk_ai_digest_welcome, approved) |

---

## Key Decisions and Rationale

1. **Gemini over Claude for WhatsApp**: Switched from Anthropic Claude to Gemini 2.5 Flash because Anthropic SDK caused dependency conflicts on Vercel. Gemini works with simple HTTP requests.

2. **Direct HTTP over SDKs**: Both Twilio and Anthropic Python SDKs caused issues on Vercel serverless. Using `requests` library for direct HTTP calls is more reliable in constrained environments.

3. **TwiML over REST API for responses**: The webhook returns inline TwiML `<Response><Message>` instead of using the Twilio REST API to send messages. This was an attempt to avoid error 63112 (did not work — the error is Meta-level, not API-level).

4. **Single-port architecture for voice**: Railway only exposes one port. Refactored from separate Flask (5005) + WebSocket (8765) to unified Starlette server handling both HTTP and WebSocket on the same port.

5. **Qwen3-30B-A3B for ElevenLabs agent**: Chosen over larger models because output token generation speed is the dominant factor in voice latency, not prompt processing speed.

6. **Sentence-boundary streaming**: Voice responses are streamed to ConversationRelay at sentence boundaries (`. `, `! `, `? `) rather than token-by-token, producing more natural-sounding speech.

---

## Pending Work

- ~~Resolve Meta/WABA error 63112~~ — RESOLVED May 2, 2026
- ~~Add `VERCEL_TOKEN` GitHub secret~~ — auto-deploy confirmed working
- Verify `+19109944861` in Meta WhatsApp Business to bring Norfolk AI Voice Digest sender online
- Google Calendar OAuth reconnection (3 accounts — Ricardo must do manually)
- Clean up the empty messaging service `MG21f0694cd1b2566a13873571d2106728`
- Known-numbers spreadsheet (Google Drive)
- Widget deployment to norfolk.ai
- Final end-to-end verification via actual phone call
- A2P Campaign registration for US long code (Twilio is prompting for this)

### Security hardening — pending (May 18, 2026)

Identified in the Phase 9 audit. Require action in external dashboards — code is already deployed.

1. **[CRITICAL] Rotate Neon database password** — `npg_FzJ7UljOwhL9` is in git history from Phase 9 ingestion scripts. Rotate in Neon console → Project Settings → Roles → neondb_owner → Reset password. Update `DATABASE_URL` in Vercel env vars immediately after.

2. **[CRITICAL] Rotate ElevenLabs API key** — `sk_8e1100d6…` was committed in `create_elevenlabs_agent.py`. Revoke in ElevenLabs dashboard → API Keys. Add new key to Vercel as `ELEVENLABS_API_KEY`.

3. **[HIGH] Wire Telegram webhook secret** — Telegram endpoint now returns 403 until configured:
   - Generate a random 32+ character string
   - Add to Vercel env as `TELEGRAM_WEBHOOK_SECRET`
   - Re-register: `GET https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://marcela-norfolk-ai.vercel.app/webhook&secret_token=<SECRET>`

4. **[HIGH] Confirm `TWILIO_AUTH_TOKEN` in Vercel** — `/webhook` now returns 403 if missing. Verify in Vercel → Settings → Environment Variables.

5. **[HIGH] Confirm `SLACK_SIGNING_SECRET` in Vercel** — Slack events are rejected if absent (endpoint now fails closed). Verify in Vercel env vars.

---

## Common Pitfalls (for Future Agents)

1. **ALWAYS check the Twilio webhook URL first** when Marcela stops responding. The most common failure mode is the webhook URL being overwritten or pointing to the wrong project. Go to Twilio > Messaging > Numbers and Senders > WhatsApp > +15559178507 > Messaging Endpoint Configuration and verify it points to `https://marcela-norfolk-ai.vercel.app/webhook`.

1b. **Error 63112 may be a red herring.** In May 2026, error 63112 appeared in logs but the actual issue was a wrong webhook URL + broken Vercel deployment. Always check the webhook URL and Vercel health endpoint BEFORE investigating Meta/WABA.

2. **Do NOT use Twilio or Anthropic Python SDKs on Vercel.** They cause dependency conflicts. Use direct HTTP requests.

3. **Do NOT use separate ports on Railway.** Only one port is exposed. Use a single-port server (Starlette handles HTTP + WebSocket on one port).

4. **Do NOT forget `python-multipart` in requirements.txt** when using Starlette/FastAPI form parsing.

5. **Do NOT assume TwiML bypasses Twilio API restrictions.** Twilio processes TwiML and sends messages via its internal API — the same restrictions apply.

6. **Do NOT skip early data collection in voice prompts.** Without explicit timing instructions, the LLM forgets to collect caller name/email.

9. **`requirements.txt` at the root is used by Vercel.** It must contain ONLY `flask` and `requests`. Voice server dependencies go in `requirements-voice.txt` (used by Dockerfile). Never merge them — the Twilio SDK and Starlette break Vercel.

10. **Vercel auto-deploy requires a GitHub secret.** The `.github/workflows/deploy.yml` workflow deploys on push but needs `VERCEL_TOKEN` set as a GitHub Actions secret in the repo settings. Without it, pushes won't deploy.

8. **Conversation history is in-memory and resets on cold start.** This is acceptable for Vercel (stateless) and Railway (infrequent restarts) but means conversations do not persist across deployments.

---

## Hardening Measures (Added May 2, 2026)

- **Health monitoring**: `scripts/health_monitor.py` runs hourly via Manus scheduler. Pings `/health` endpoint and sends WhatsApp alert to Ricardo (+15126699705) if Marcela is down.
- **No hardcoded credentials**: All credential fallbacks removed from `api/index.py`. Credentials live only in Vercel environment variables.
- **GitHub Actions auto-deploy**: `.github/workflows/deploy.yml` deploys to Vercel on every push to master/main. Requires `VERCEL_TOKEN` GitHub secret.
- **CE Compound Engineering skills**: 38 skills + 49 agents installed in `skills/compound-engineering/` from EveryInc/compound-engineering-plugin.
- **Separate requirements files**: `requirements.txt` (Vercel — flask + requests only) and `requirements-voice.txt` (Railway — full voice stack).

---

## CE Compound Engineering Skills

Installed from [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) into `skills/compound-engineering/`.

**38 skills** including: `ce-plan`, `ce-work`, `ce-compound`, `ce-code-review`, `ce-debug`, `ce-commit`, `ce-ideate`, `ce-brainstorm`, `ce-optimize`, `ce-simplify-code`, `ce-setup`, `ce-sessions`, `ce-update`, `ce-proof`, `ce-strategy`, and more.

**49 agents** including adversarial reviewers, architecture strategist, API contract reviewer, correctness reviewer, deployment verification agent, and more.

The CE workflow: **Plan → Work → Review → Commit** — agents learn from every session so code quality compounds over time.

---

## Voice AI Community Intelligence

- **Pipecat AI Discord** (17k+ users): Largest open voice AI community
- **Key insight**: Endpointing (turn detection) is the most-discussed optimization challenge across all platforms
- **Platform comparison**: ElevenLabs most stable; VAPI most active dev community; Retell and Bland have more latency complaints

---

## Phase 9: Neon pgvector RAG + Persistent Memory + Mel Robbins Voice (May 4, 2026)

**Commits**: `b6ed060`, `5399b27`, `3ece1f0`, `e7b1917`

### What Was Built

1. **Neon PostgreSQL + pgvector** wired into Marcela as the persistent data layer:
   - `conversations` table: stores every message (user + assistant) per platform/user, survives cold starts
   - `knowledge_base` table: 105 chunks from 6 Norfolk AI documents, embedded with Gemini `gemini-embedding-001` (3072 dims), indexed with HNSW via `halfvec` type (pgvector 0.8+)

2. **RAG pipeline**: On every message, Marcela embeds the query, runs cosine similarity search against `knowledge_base`, and injects the top-3 relevant chunks into the system prompt as grounding context.

3. **Persistent conversation memory**: Last 10 turns per user/platform are fetched from Neon and prepended to the Gemini context window, giving Marcela true cross-session memory.

4. **Mel Robbins voice**: System prompt rewritten across all platforms (WhatsApp, Slack, Telegram) to reflect Mel Robbins' communication style — direct, warm, no-nonsense, action-oriented, uses "you" language, short punchy sentences, occasional wit, never preachy.

5. **Telegram bot**: `@MarcelaNorfolkAI_bot` created and webhook registered at `https://marcela-norfolk-ai.vercel.app/webhook`.

### Knowledge Base Documents (6 files, 105 chunks)

| File | Description |
|---|---|
| `NorfolkAISolutionsOverview.docx` | Norfolk AI services, capabilities, and offerings |
| `norfolk-ai-content.md` | Website content and messaging |
| `KnowledgeBenefitsofAIAgents1.pdf` | Benefits of AI agents whitepaper |
| `SuperConversationsKnowledgeBase2.pdf` | Super Conversations KB |
| `WhatAreSuperConversations.pdf` | Super Conversations explainer |
| `SuperConversationsastheFoundation....docx` | Super Conversations for business/sales/AI training |

### Neon Database Schema

```sql
-- pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Conversation memory (persistent across cold starts)
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,  -- 'whatsapp', 'slack', 'telegram'
    user_id VARCHAR(255) NOT NULL,
    role VARCHAR(10) NOT NULL,       -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(platform, user_id, created_at DESC);

-- Knowledge base with pgvector embeddings
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    source VARCHAR(255),
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding vector(3072),
    embedding_half halfvec(3072),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_kb_hnsw ON knowledge_base USING hnsw (embedding_half halfvec_cosine_ops);
```

### RAG Architecture

```
User message
    │
    ▼
Embed query (gemini-embedding-001, 3072 dims)
    │
    ▼
Cosine similarity search → knowledge_base (top 3 chunks)
    │
    ▼
Fetch last 10 turns → conversations table
    │
    ▼
Build Gemini prompt:
  [System: Mel Robbins voice + RAG context]
  [History: last 10 turns]
  [User: current message]
    │
    ▼
Gemini 2.5 Flash response
    │
    ▼
Save to conversations table
    │
    ▼
Send reply (WhatsApp TwiML / Slack API / Telegram API)
```

### Critical Lessons Learned (May 4, 2026)

1. **`api/requirements.txt` is what Vercel uses, NOT root `requirements.txt`**. The `@vercel/python` builder looks for `requirements.txt` in the same directory as the function file (`api/`). The root `requirements.txt` is ignored. **Always update `api/requirements.txt` for Vercel dependencies.**

2. **pgvector HNSW index has a 2000-dimension limit**. For 3072-dim embeddings (Gemini), use `halfvec` type + HNSW: `CREATE INDEX ... USING hnsw (embedding_half halfvec_cosine_ops)`. The `halfvec` type supports up to 4000 dims.

3. **Neon pooler SSL EOF on bulk inserts**. The Neon connection pooler (PgBouncer) drops connections after ~30s idle or on large transactions. Fix: insert rows one at a time with reconnect logic between batches.

4. **Vercel build caching**: Vercel caches the pip install layer. A 7-second build means it's using cache. To force a full rebuild, change both `api/requirements.txt` AND `api/index.py` in the same commit.

5. **`channel_binding=require` in Neon URL**: Both psycopg2 connection modes (with and without `channel_binding=require`) work fine from the sandbox. No issues with this parameter.

6. **GitHub PAT scopes**: Fine-grained tokens with `push: true` in permissions still cannot push via `git push` over HTTPS — they lack OAuth scopes. Use a **classic PAT with `repo` scope** for git push operations.

### Environment Variables Added (Vercel)

| Variable | Description |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL connection string (pooler endpoint, sslmode=require) |
| `GITHUB_TOKEN` | GitHub PAT for any future GitHub API operations from functions |

### Telegram Bot

| Item | Value |
|---|---|
| Bot username | `@MarcelaNorfolkAI_bot` |
| Bot URL | `t.me/MarcelaNorfolkAI_bot` |
| Webhook | `https://marcela-norfolk-ai.vercel.app/webhook` |
| Token env var | `TELEGRAM_BOT_TOKEN` (needs to be added to Vercel) |

**Note**: `TELEGRAM_BOT_TOKEN` still needs to be added to Vercel env vars for Telegram to work end-to-end.

---

## Updated Architecture Summary (May 4, 2026)

| Component | Technology | Deployment |
|---|---|---|
| WhatsApp Agent | Flask + Gemini 2.5 Flash + Neon RAG | Vercel Serverless (`api/index.py`) |
| Slack Agent | Flask + Gemini 2.5 Flash + Neon RAG | Vercel Serverless (`api/index.py`) |
| Telegram Agent | Flask + Gemini 2.5 Flash + Neon RAG | Vercel Serverless (`api/index.py`) |
| Voice Agent | Starlette + Gemini 2.5 Flash (streaming) + ConversationRelay | Railway (Docker container) |
| Persistent Memory | Neon PostgreSQL (`conversations` table) | Neon serverless |
| Knowledge Base | Neon pgvector (`knowledge_base` table, 105 chunks) | Neon serverless |
| Embeddings | Gemini `gemini-embedding-001` (3072 dims) | Google AI API |
| STT | Deepgram nova-3-general | Via Twilio ConversationRelay |
| TTS | ElevenLabs Flash 2.5 | Via Twilio ConversationRelay |
| LLM | Google Gemini 2.5 Flash | Direct API |
| Telephony | Twilio | WhatsApp Messaging + Voice ConversationRelay |

---

## Updated Common Pitfalls

9b. **`api/requirements.txt` is the Vercel requirements file, NOT root `requirements.txt`.** Always add new Python packages to `api/requirements.txt`. The root file is a legacy artifact.

9c. **pgvector HNSW index fails for >2000 dims.** Use `halfvec` column + `halfvec_cosine_ops` for Gemini embeddings (3072 dims).

9d. **Neon pooler drops connections on bulk operations.** Insert rows one at a time with reconnect logic. Do not use `executemany()` with large batches.
