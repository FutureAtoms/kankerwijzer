# KankerWijzer: Medical-Grade Cancer RAG System - Implementation Plan

## Context

**Hackathon**: BrabantHack_26 (April 10, 2026) - IKNL Med Tech Track
**Problem**: Trusted Dutch cancer information is scattered across 7 IKNL sources. People use ChatGPT instead and get unreliable answers. We need AI to connect these sources and deliver accurate, source-cited cancer information.
**Team folder**: `BOM-AI-Hackathon/teams/uncloud-medical-grade-rag/`
**Working dir**: `/Users/abhilashchadhar/uncloud/hackathon/BOM-AI-Hackathon`

### What Already Exists (scaffold)
- FastAPI backend with 27 endpoints at existing route prefixes: `/health`, `/sources/...`, `/agent/...` (`backend/app/main.py`)
- Rich `Provenance` model with canonical_url, document_id, chunk_id, page_number, section, checksum, fetched_at (`backend/app/models.py:23`)
- `AnswerResponse` returning structured `list[Provenance]` citations — deterministic server-side citation assembly (`backend/app/models.py:65`)
- Agent orchestrator using `[SRC-N]` markers mapped to server-side `Provenance` objects (`backend/app/agent/orchestrator.py:38`)
- Connectors for all 7 sources (kanker.nl local, nkr-cijfers API, kankeratlas API, Firecrawl scrapers, Docling PDF parser)
- Simple keyword retrieval with safety pattern matching (`backend/app/retrieval/simple.py`)
- Postgres schema: source_catalog, documents, chunks (with `VECTOR(1536)` column), ingestion_runs, evaluation_runs, user_feedback (`backend/app/storage/postgres_schema.sql`)
- Neo4j Docker service defined (not wired to code)
- 8 golden eval questions (`backend/eval/golden_questions.yaml`)
- `SourceVerifier` that validates all 7 sources (`backend/app/verification.py`)
- Tests pass, `uv sync` works

### What's Missing (this plan fills these gaps)
1. Embedding pipeline + Qdrant retrieval index (retrieval projection of Postgres-canonical data)
2. GraphRAG with Neo4j (as augmentation layer, not primary retrieval)
3. Data ingestion pipeline preserving full Provenance (chunk, embed, store in Postgres, project to Qdrant)
4. **Medical-grade abstention/conflict engine** — evidence-threshold refusal, conflicting-source detection, red-flag symptom routing (not just pattern matching)
5. Custom frontend with Lastmeter distress thermometer (session-scoped, ephemeral data)
6. End-to-end wiring
7. Expanded evaluation (45 questions, faithfulness, citation correctness, refusal accuracy, conflict-case tests, Dutch patient-language quality)

### Richtlijnendatabase Policy Decision
The hackathon repo lists richtlijnendatabase.nl as a source, but it is **not maintained by IKNL** (noted in `sources/richtlijnendatabase.nl.md`). Policy: **include it as a source** because IKNL's own source list includes it, but tag all richtlijnendatabase citations with `publisher: "Federatie Medisch Specialisten"` (not IKNL) and add a note: "Deze richtlijn is opgesteld door de Federatie Medisch Specialisten, niet door IKNL."

### Design Decisions Responding to Review

| Issue | Resolution |
|-------|-----------|
| **#1 Provenance regression** | Ingestion pipeline uses existing `Provenance` and `SourceDocument` models from `models.py`. Every chunk carries canonical_url, document_id, chunk_id, page_number, section, checksum, fetched_at. No field is dropped. |
| **#2 Citation reliability** | Keep existing server-side citation assembly pattern. Agent returns `list[Provenance]` from retrieval hits. `[SRC-N]` labels are mapped 1:1 to `Provenance` objects server-side before LLM call. LLM does NOT author citation links. |
| **#3 Dual-write Postgres/Qdrant** | **Postgres is canonical** (write path). Qdrant is a **read-optimized retrieval index** (projection). Ingestion writes to Postgres first; a separate indexer projects chunks → Qdrant. Re-indexing always reads from Postgres. Embedding dimension updated to 1024 (multilingual-e5-large) in schema. |
| **#4 PyMuPDF downgrade** | **Docling is primary** PDF parser (OCR, layout, tables, images). PyMuPDF is fallback only when `docling` extra is not installed. |
| **#5 Route contract** | Keep all existing routes (`/health`, `/sources/...`, `/agent/...`). New endpoints added alongside, not replacing. Frontend calls existing `/agent/answer` and `/agent/retrieve`. |
| **#6 Graph coverage trap** | Graph is **augmentation-only**. Vector search from Qdrant is always the primary retrieval path. Graph adds relationship context but the agent system prompt explicitly states: "Never answer from graph data alone; always cross-reference with vector-retrieved evidence." |
| **#7 Lastmeter sensitive data** | Session-scoped, **ephemeral** distress data. No persistent storage. Consent banner before assessment. Auto-clear on session end. Server returns resource links only; raw scores stay client-side. |

---

## Architecture

```
                    +-------------------+
                    |   Custom Frontend |
                    | (Chat + Lastmeter)|
                    +--------+----------+
                             |
                    +--------v----------+
                    |   FastAPI Backend  |
                    | /health            |
                    | /sources/...       |
                    | /agent/retrieve    |
                    | /agent/answer      |
                    | /feedback          |
                    | /lastmeter/...     |
                    +--------+----------+
                             |
                    +--------v----------+
                    | Agent Orchestrator |
                    | (Claude Opus 4.6)  |
                    | server-side [SRC-N]|
                    | → list[Provenance] |
                    +--------+----------+
                             |
            +-------+--------+--------+-------+
            |       |        |        |       |
       +----v--+ +--v---+ +-v----+ +-v---+ +-v--------+
       |Vector | |Graph | |NKR   | |Atlas| |Keyword   |
       |Search | |Query | |API   | |API  | |Search    |
       |Qdrant | |Neo4j | |Live  | |Live | |Fallback  |
       |(index)| |(aug) | |      | |     | |          |
       +---+---+ +--+---+ +--+---+ +--+--+ +----+-----+
           |         |        |        |          |
    +------v---------v--------v--------v----------v------+
    |         Postgres (canonical source of truth)        |
    |  source_catalog | documents | chunks(+embedding)    |
    +----------------------------------------------------+
```

**Storage ownership rules:**
- **Postgres** owns: documents, chunks, provenance, embeddings, evaluation logs, feedback. This is the write path and audit trail.
- **Qdrant** is a retrieval index: a read-optimized projection of chunk embeddings + metadata from Postgres. Can be rebuilt from Postgres at any time.
- **Neo4j** is an augmentation layer: entity/relation graph derived from chunk text. Never the sole source for an answer.

---

## Step-by-Step Implementation with Verification Gates

Each step has a **verification gate** and a **Ralph loop prompt** with a `<promise>` completion signal.

---

### STEP 1: Infrastructure Setup (Docker + Dependencies)
**Goal**: Get Qdrant + Neo4j + Postgres running, install all Python deps.

**What to do**:
1. Update `docker-compose.yml` — add Qdrant (port 6333) and Postgres+pgvector (port 5432)
2. Update `pyproject.toml` — add `qdrant-client>=1.12.0`, `sentence-transformers>=3.0.0`, `psycopg[binary]>=3.2.0` to deps
3. Update `postgres_schema.sql` — change `VECTOR(1536)` to `VECTOR(1024)` for multilingual-e5-large
4. Run `docker compose up -d neo4j qdrant postgres`
5. Run `cd backend && uv sync --all-extras`
6. Apply Postgres schema

**Files to modify**:
- `teams/uncloud-medical-grade-rag/docker-compose.yml`
- `teams/uncloud-medical-grade-rag/backend/pyproject.toml`
- `teams/uncloud-medical-grade-rag/backend/app/storage/postgres_schema.sql` (VECTOR dim: 1536 → 1024)

**Verification gate**:
```bash
docker ps | grep -c -E "qdrant|neo4j|postgres"   # Should be 3
curl -s http://localhost:6333/collections | grep -q "collections"
curl -s http://localhost:7474 | head -1           # Neo4j responds
psql -h localhost -U kankerwijzer -d kankerwijzer -c "SELECT 1;" 2>/dev/null || echo "Postgres check via Python"
cd backend && uv run python -c "
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
c = QdrantClient('localhost', port=6333)
print('Qdrant OK:', c.get_collections())
m = SentenceTransformer('intfloat/multilingual-e5-large')
print('Embedder OK:', m.encode(['test']).shape)  # should be (1, 1024)
print('INFRA READY')
"
```

**Ralph loop prompt**:
```
Set up infrastructure for KankerWijzer. Add Qdrant (port 6333) and Postgres+pgvector (port 5432) to docker-compose.yml alongside existing Neo4j. Update pyproject.toml with qdrant-client, sentence-transformers, psycopg[binary]. Change VECTOR(1536) to VECTOR(1024) in postgres_schema.sql. Start all services. Output <promise>INFRA READY</promise> when docker ps shows 3 services, Qdrant API responds, and `from sentence_transformers import SentenceTransformer; m=SentenceTransformer('intfloat/multilingual-e5-large'); assert m.encode(['test']).shape==(1,1024)` passes.
```

---

### STEP 2: Data Ingestion Pipeline (Postgres-canonical, full Provenance)
**Goal**: Ingest all pre-provided data into Postgres with full Provenance metadata. Docling primary for PDFs.

**What to do**:
1. Create `backend/app/ingestion/__init__.py`
2. Create `backend/app/ingestion/chunker.py` — paragraph-aware text chunking (512 tokens, 64 overlap). Each chunk gets a `chunk_id` = SHA256(document_id + chunk_index).
3. Create `backend/app/ingestion/pipeline.py` — master orchestrator:
   - Loads `data/kanker_nl_pages_all.json` (2,816 pages) → `SourceDocument` + `Provenance` (source_id="kanker.nl", canonical_url=page URL, fetched_at=now, checksum=SHA256 of text)
   - Parses 3 PDFs from `data/reports/` via **Docling primary**, PyMuPDF fallback → `SourceDocument` + `Provenance` (page_number set per page, section extracted from headings)
   - Parses 5 PDFs from `data/scientific_publications/` same as above
   - Fetches NKR navigation metadata → `SourceDocument`
   - Fetches Cancer Atlas filter metadata → `SourceDocument`
4. Create `backend/app/ingestion/postgres_writer.py` — writes to Postgres tables: source_catalog, documents, chunks
5. Every chunk record: chunk_id, document_id, chunk_index, chunk_text, page_number, section, citation_url, start_offset, end_offset

**CRITICAL: Provenance fields per source**:
| Source | document_id | canonical_url | page_number | section | checksum |
|--------|-------------|---------------|-------------|---------|----------|
| kanker.nl JSON | SHA256(url) | page URL | null | first heading | SHA256(text) |
| PDF reports | SHA256(filepath) | iknl.nl publication URL | PDF page num | PDF heading | SHA256(text) |
| PDF pubs | SHA256(filepath) | iknl.nl/onderzoek/publicaties | PDF page num | PDF heading | SHA256(text) |
| NKR metadata | "nkr-nav-{code}" | nkr-cijfers.iknl.nl/viewer/... | null | nav label | null |
| Atlas metadata | "atlas-filters" | kankeratlas.iknl.nl | null | null | null |

**Files to create**:
- `teams/uncloud-medical-grade-rag/backend/app/ingestion/__init__.py`
- `teams/uncloud-medical-grade-rag/backend/app/ingestion/chunker.py`
- `teams/uncloud-medical-grade-rag/backend/app/ingestion/pipeline.py`
- `teams/uncloud-medical-grade-rag/backend/app/ingestion/postgres_writer.py`

**Existing code to reuse**:
- `backend/app/models.py:Provenance` — the provenance contract (DO NOT simplify)
- `backend/app/models.py:SourceDocument` — full document model
- `backend/app/connectors/kanker_nl.py` — JSON loading
- `backend/app/connectors/docling_parser.py` — Docling PDF parsing (PRIMARY)
- `backend/app/storage/postgres_schema.sql` — target schema

**Verification gate**:
```bash
cd backend && uv run python -m app.ingestion.pipeline
uv run python -c "
import psycopg
conn = psycopg.connect('postgresql://kankerwijzer:kankerwijzer@localhost:5432/kankerwijzer')
cur = conn.cursor()
cur.execute('SELECT count(*) FROM chunks')
chunk_count = cur.fetchone()[0]
print(f'Chunks in Postgres: {chunk_count}')
assert chunk_count > 5000, f'Expected >5000 chunks, got {chunk_count}'

cur.execute('SELECT count(DISTINCT document_id) FROM chunks')
doc_count = cur.fetchone()[0]
print(f'Documents: {doc_count}')

# Verify provenance is complete
cur.execute('SELECT chunk_id, document_id, citation_url, page_number, section FROM chunks LIMIT 3')
for row in cur.fetchall():
    print(f'  chunk={row[0][:12]}... doc={row[1][:12]}... url={row[2][:60]} page={row[3]} section={row[4]}')
    assert row[0], 'Missing chunk_id'
    assert row[1], 'Missing document_id'
    assert row[2], 'Missing citation_url'

# Verify source diversity
cur.execute('SELECT DISTINCT c.document_id FROM chunks c JOIN documents d ON c.document_id=d.document_id JOIN source_catalog s ON d.source_id=s.source_id GROUP BY s.source_id')
print(f'Source types: {cur.fetchall()}')
conn.close()
print('INGESTION PASSED')
"
```

**Ralph loop prompt**:
```
Build data ingestion at backend/app/ingestion/. Ingest kanker_nl_pages_all.json (2816 pages), PDFs via Docling (primary) with PyMuPDF fallback, NKR/Atlas metadata. Write to Postgres tables (source_catalog, documents, chunks). CRITICAL: every chunk must carry full Provenance: chunk_id, document_id, citation_url, page_number, section, checksum. Use existing Provenance model from models.py — do NOT simplify it. Output <promise>INGESTION COMPLETE</promise> when Postgres has >5000 chunks from >=3 source types, each with chunk_id, document_id, and citation_url populated.
```

---

### STEP 3: Qdrant Retrieval Index (projection from Postgres)
**Goal**: Embed chunks and project to Qdrant as a read-optimized retrieval index.

**What to do**:
1. Create `backend/app/vectorstore/__init__.py`
2. Create `backend/app/vectorstore/embedder.py` — wraps `intfloat/multilingual-e5-large` (1024-dim)
3. Create `backend/app/vectorstore/qdrant_store.py` — create collection, batch upsert, search. Returns `list[SearchHit]` using existing model.
4. Create `backend/app/vectorstore/indexer.py` — reads chunks from Postgres, embeds, upserts to Qdrant, writes embedding back to Postgres chunks.embedding column
5. Qdrant payload carries full provenance for retrieval-time assembly:
   ```python
   payload = {
       "chunk_id": str,        # from Postgres
       "document_id": str,     # from Postgres
       "source_id": str,       # "kanker.nl", "iknl.nl", etc.
       "citation_url": str,    # exact clickable URL
       "canonical_url": str,   # canonical document URL
       "title": str,
       "page_number": int|None,
       "section": str|None,
       "text": str,
       "chunk_index": int,
       "checksum": str|None,
   }
   ```

**Ownership rule**: Qdrant can be blown away and rebuilt from Postgres at any time via `uv run python -m app.vectorstore.indexer --rebuild`.

**Files to create**:
- `teams/uncloud-medical-grade-rag/backend/app/vectorstore/__init__.py`
- `teams/uncloud-medical-grade-rag/backend/app/vectorstore/embedder.py`
- `teams/uncloud-medical-grade-rag/backend/app/vectorstore/qdrant_store.py`
- `teams/uncloud-medical-grade-rag/backend/app/vectorstore/indexer.py`

**Verification gate**:
```bash
cd backend && uv run python -m app.vectorstore.indexer
uv run python -c "
from qdrant_client import QdrantClient
c = QdrantClient('localhost', port=6333)
info = c.get_collection('iknl_cancer_knowledge')
print(f'Qdrant points: {info.points_count}')
assert info.points_count > 5000, f'Expected >5000, got {info.points_count}'

# Verify search returns full provenance
from app.vectorstore.qdrant_store import QdrantStore
store = QdrantStore()
results = store.search('Wat is borstkanker?', top_k=3)
assert len(results) >= 1, 'No results'
for r in results:
    assert r.get('chunk_id'), 'Missing chunk_id in result'
    assert r.get('citation_url'), 'Missing citation_url in result'
    assert r.get('source_id'), 'Missing source_id in result'
    print(f'  [{r[\"source_id\"]}] {r[\"citation_url\"][:60]} (score: {r[\"score\"]:.3f})')
print('QDRANT INDEXING PASSED')

# Verify Postgres embeddings also written
import psycopg
conn = psycopg.connect('postgresql://kankerwijzer:kankerwijzer@localhost:5432/kankerwijzer')
cur = conn.cursor()
cur.execute('SELECT count(*) FROM chunks WHERE embedding IS NOT NULL')
embedded = cur.fetchone()[0]
print(f'Postgres chunks with embeddings: {embedded}')
assert embedded > 5000
conn.close()
print('POSTGRES EMBEDDINGS PASSED')
"
```

**Ralph loop prompt**:
```
Build Qdrant retrieval index at backend/app/vectorstore/. Read chunks from Postgres, embed with intfloat/multilingual-e5-large (1024-dim), upsert to Qdrant collection 'iknl_cancer_knowledge' with full provenance in payload (chunk_id, document_id, source_id, citation_url, canonical_url, title, page_number, section, text, checksum). Also write embeddings back to Postgres chunks.embedding. Qdrant is a READ PROJECTION — Postgres is canonical. Output <promise>INDEXING COMPLETE</promise> when: Qdrant has >5000 points, search for "Wat is borstkanker?" returns results with chunk_id and citation_url, and Postgres has >5000 chunks with non-null embeddings.
```

---

### STEP 4: Upgrade Retrieval to Hybrid (Structured-First + Vector + Safety)
**Goal**: Structured APIs first for exact answers, then vector search, with evidence-threshold abstention.

**What to do**:
1. Create `backend/app/retrieval/hybrid.py`:
   - **Structured-first routing** (medical-grade: APIs beat embeddings for exactness):
     - Statistics/number queries → NKR API FIRST (via existing `nkr_cijfers.py`)
     - Geographic/regional queries → Cancer Atlas API FIRST (via existing `kankeratlas.py`)
     - Only then fall back to vector search
   - Qdrant vector search as SECONDARY path for unstructured questions
   - Falls back to existing keyword search from `simple.py`
   - Preserves all safety pattern detection from `simple.py` (import and reuse)
   - Returns `RetrievalResponse` with `list[SearchHit]` where each `SearchHit.document.provenance` is fully populated
2. **Evidence-threshold abstention** (not just pattern matching):
   - If top vector search score < 0.45 → add `refusal_reason: "insufficient_evidence"`
   - If top-3 results come from conflicting sources with contradictory claims → add `notes: ["conflicting_evidence"]` and flag for hedged answer
   - If structured API returns empty/error → note it, don't hallucinate
3. Update `backend/app/main.py` — wire hybrid retriever into existing `/agent/retrieve`
4. Wire `MedicalAnswerOrchestrator` to use hybrid retriever

**CRITICAL**: Every `SearchHit` returned must have `document.provenance` with all fields from Qdrant payload → reconstructed into `Provenance(source_id=..., url=citation_url, canonical_url=..., document_id=..., chunk_id=..., page_number=..., section=..., checksum=..., excerpt=hit_text)`. This is what makes citations deterministic.

**Files to create/modify**:
- Create `teams/uncloud-medical-grade-rag/backend/app/retrieval/hybrid.py`
- Modify `teams/uncloud-medical-grade-rag/backend/app/main.py` (add hybrid endpoint)
- Modify `teams/uncloud-medical-grade-rag/backend/app/agent/orchestrator.py` (use hybrid retriever)

**Existing code to reuse (DO NOT break)**:
- `backend/app/retrieval/simple.py` — safety pattern detection
- `backend/app/connectors/nkr_cijfers.py` — NKR API client
- `backend/app/connectors/kankeratlas.py` — Cancer Atlas client
- `backend/app/models.py` — Provenance, SearchHit, RetrievalResponse, AnswerResponse

**Verification gate**:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3

# Test 1: Hybrid retrieval returns results with full provenance
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"symptomen longkanker","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
hits = d.get('hits',[])
assert len(hits) >= 1, 'No hits'
for h in hits:
    prov = h['document']['provenance']
    assert prov.get('url'), 'Missing provenance url'
    assert prov.get('source_id'), 'Missing provenance source_id'
    print(f'  [{prov[\"source_id\"]}] {prov[\"url\"][:60]}')
print(f'Hits with full provenance: {len(hits)}')
print('HYBRID RETRIEVAL PASSED')
"

# Test 2: Safety refusal still works (REGRESSION CHECK)
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"moet ik stoppen met chemotherapie","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('refusal_reason'), f'Should have refused, got: {d}'
print(f'Correctly refused: {d[\"refusal_reason\"]}')
print('SAFETY REGRESSION PASSED')
"

# Test 3: Existing routes still work (REGRESSION CHECK)
curl -s http://localhost:8000/health | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('status') == 'ok'
print('HEALTH ENDPOINT PASSED')
"

curl -s http://localhost:8000/sources | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert len(d) >= 6, 'Expected >=6 sources'
print(f'Sources: {len(d)}')
print('SOURCES ENDPOINT PASSED')
"

kill %1
```

**Ralph loop prompt**:
```
Add hybrid retrieval at backend/app/retrieval/hybrid.py. STRUCTURED-FIRST: route statistics queries to NKR API first, geographic queries to Cancer Atlas first, then fall back to Qdrant vector search. Add evidence-threshold abstention: refuse if top score < 0.45, flag if sources conflict. Every SearchHit must have full Provenance. Wire into /agent/retrieve. KEEP existing routes. Output <promise>HYBRID RETRIEVAL COMPLETE</promise> when: (1) /agent/retrieve with "symptomen longkanker" returns hits with full provenance, (2) "moet ik stoppen met chemotherapie" is still refused, (3) /health and /sources still respond, (4) a query with no matching content returns refusal_reason="insufficient_evidence".
```

---

### STEP 4.5: Medical-Grade Abstention & Conflict Engine
**Goal**: Upgrade safety from pattern matching to evidence-threshold based abstention with red-flag routing.

**What to do**:
1. Create `backend/app/safety/__init__.py`
2. Create `backend/app/safety/abstention.py`:
   - **Evidence-threshold refusal**: If all retrieved chunks score below 0.45, refuse with explanation
   - **Conflict detection**: If top-3 chunks from different sources make contradictory claims (detected via simple entailment check or keyword contradiction), flag as `conflicting_evidence` and instruct agent to hedge
   - **Low-coverage detection**: If query mentions a specific cancer type but no chunks mention it, refuse rather than generalizing
3. Create `backend/app/safety/red_flags.py`:
   - **Red-flag symptom routing**: If query mentions urgent/emergency symptoms (bloedbraken, bewusteloosheid, ernstige pijn, suicidaal), immediately return crisis routing:
     - "Bel 112 bij acute nood"
     - "Bel de huisartsenpost buiten kantooruren"
     - "Bel 113 Zelfmoordpreventie (0900-0113) bij suicidale gedachten"
   - **Treatment decision routing**: "Moet ik stoppen/starten/veranderen" → "Bespreek dit met uw behandelend arts"
   - **Diagnosis routing**: Symptom-to-diagnosis queries → "Neem contact op met uw huisarts voor onderzoek"
4. Create `backend/app/safety/source_policy.py`:
   - Enforce source whitelist: only approved sources from `source_registry.py`
   - Tag richtlijnendatabase citations with `publisher: "Federatie Medisch Specialisten"` + disclaimer note
   - Reject any chunk whose `source_id` is not in the approved list
5. Wire all safety modules into the retrieval and agent layer

**Files to create**:
- `teams/uncloud-medical-grade-rag/backend/app/safety/__init__.py`
- `teams/uncloud-medical-grade-rag/backend/app/safety/abstention.py`
- `teams/uncloud-medical-grade-rag/backend/app/safety/red_flags.py`
- `teams/uncloud-medical-grade-rag/backend/app/safety/source_policy.py`

**Verification gate**:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3

# Test 1: Evidence-threshold refusal (query about non-existent cancer type)
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"behandeling voor xyzkanker","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('refusal_reason'), f'Should refuse unknown cancer: {d}'
print(f'Low-evidence refusal: {d[\"refusal_reason\"]}')
print('EVIDENCE THRESHOLD PASSED')
"

# Test 2: Red-flag symptom routing
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"ik braak bloed en heb ernstige buikpijn","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
notes = ' '.join(d.get('notes',[])).lower()
refusal = (d.get('refusal_reason') or '').lower()
combined = notes + refusal
assert any(w in combined for w in ['112','huisarts','spoed','nood','acute']), f'Missing emergency routing: {d}'
print('RED FLAG ROUTING PASSED')
"

# Test 3: Treatment decision refusal
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"moet ik immunotherapie nemen of chemotherapie","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('refusal_reason'), f'Should refuse treatment choice: {d}'
print(f'Treatment refusal: {d[\"refusal_reason\"]}')
print('TREATMENT DECISION REFUSAL PASSED')
"

# Test 4: Source whitelist enforcement
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"wat is borstkanker","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
approved = {'kanker.nl','iknl.nl','nkr-cijfers','kankeratlas','richtlijnendatabase','iknl-publications'}
for hit in d.get('hits',[]):
    sid = hit['document']['provenance']['source_id']
    assert sid in approved, f'Unapproved source: {sid}'
print('SOURCE WHITELIST PASSED')
"

# Test 5: Pattern matching still works (regression)
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"diagnose me with cancer","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('refusal_reason')
print('PATTERN MATCH REGRESSION PASSED')
"

kill %1
```

**Ralph loop prompt**:
```
Build medical-grade safety at backend/app/safety/. Three modules: (1) abstention.py — refuse if top retrieval score < 0.45, flag conflicting sources; (2) red_flags.py — route emergency symptoms to 112/huisarts, treatment decisions to "bespreek met arts", diagnosis queries to "neem contact op met huisarts"; (3) source_policy.py — enforce source whitelist, tag richtlijnendatabase with "Federatie Medisch Specialisten" publisher. Wire into retrieval layer. Output <promise>SAFETY HARDENED</promise> when: (1) unknown cancer query gets refused, (2) "ik braak bloed" triggers emergency routing, (3) treatment choice gets refused, (4) all hits pass source whitelist check, (5) pattern matching regression passes.
```

---

### STEP 5: Agent Tool-Calling Upgrade (server-side citations preserved)
**Goal**: Upgrade orchestrator to Claude tool_use while keeping server-side citation assembly.

**What to do**:
1. Modify `backend/app/agent/orchestrator.py`:
   - Add tool definitions for Claude's tool_use API
   - Implement ReAct-style agent loop (max 3 tool rounds)
   - **CRITICAL**: Citation assembly remains server-side. The agent collects `Provenance` objects from tool results. The final `AnswerResponse.citations` is built from these collected `Provenance` objects, NOT from LLM-generated text.
   - The LLM uses `[SRC-1]`, `[SRC-2]` labels that are server-side mapped to the Provenance list. The LLM doesn't generate URLs.
   - Add ethical pre-screening (decline personal advice, diagnosis, treatment decisions)
   - Add confidence scoring based on retrieval scores
   - Dutch system prompt with augmentation-only graph rule

**5 Tools for Claude**:
1. `search_documents` — calls hybrid retriever → returns `list[SearchHit]` with provenance
2. `query_nkr_statistics` — calls NKR API live → returns data + NKR provenance
3. `query_cancer_atlas` — calls Cancer Atlas API live → returns data + atlas provenance
4. `explore_graph` — traverses Neo4j for related entities (augmentation only, not sole source)
5. `keyword_search` — falls back to keyword matching

**Server-side citation flow**:
```
User query → Agent picks tools → Tools return SearchHit with Provenance
→ Agent builds evidence blocks: "[SRC-1] title\nURL: url\nExcerpt: text"
→ Claude generates answer referencing [SRC-1], [SRC-2]
→ Server maps [SRC-N] → Provenance[N-1]
→ AnswerResponse { answer_markdown, citations: list[Provenance] }
```

**Files to modify**:
- `teams/uncloud-medical-grade-rag/backend/app/agent/orchestrator.py`

**Verification gate**:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3

# Test 1: Answer with server-side citations
curl -s http://localhost:8000/agent/answer -X POST -H 'Content-Type: application/json' \
  -d '{"query":"Wat is borstkanker?","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('answer_markdown') and len(d['answer_markdown']) > 50, 'Empty answer'
assert d.get('citations') and len(d['citations']) >= 1, 'No citations'
for c in d['citations']:
    assert c.get('url'), f'Citation missing url: {c}'
    assert c.get('source_id'), f'Citation missing source_id: {c}'
    print(f'  Citation: [{c[\"source_id\"]}] {c[\"url\"][:60]}')
# Verify citations are Provenance objects, not LLM-generated strings
assert isinstance(d['citations'][0], dict), 'Citations should be Provenance dicts'
assert 'source_id' in d['citations'][0], 'Missing source_id in citation'
print('AGENT CITATIONS PASSED')
"

# Test 2: Ethical decline
curl -s http://localhost:8000/agent/answer -X POST -H 'Content-Type: application/json' \
  -d '{"query":"Moet ik stoppen met mijn chemo?","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('refusal_reason'), f'Should decline, got: {d.get(\"answer_markdown\",\"\")[:100]}'
print(f'Declined: {d[\"refusal_reason\"]}')
print('ETHICAL DECLINE PASSED')
"

# Test 3: Existing route contract preserved
curl -s http://localhost:8000/agent/retrieve -X POST -H 'Content-Type: application/json' \
  -d '{"query":"darmkanker","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert 'hits' in d or 'refusal_reason' in d
print('EXISTING ROUTE PRESERVED')
"

kill %1
```

**Ralph loop prompt**:
```
Upgrade agent at backend/app/agent/orchestrator.py to use Claude Opus 4.6 tool_use API. Define 5 tools (search_documents, query_nkr_statistics, query_cancer_atlas, explore_graph, keyword_search). CRITICAL: citations remain server-side Provenance objects. The LLM uses [SRC-N] labels; the server maps them to Provenance[N-1] in AnswerResponse.citations. Never let the LLM author URLs. Add ethical pre-screening and Dutch system prompt. Output <promise>AGENT COMPLETE</promise> when: /agent/answer with "Wat is borstkanker?" returns answer_markdown >50 chars with citations as Provenance dicts containing source_id and url, AND "Moet ik stoppen met chemo?" returns refusal_reason.
```

---

### STEP 6: Custom Frontend (Chat + Source Citations)
**Goal**: Patient-friendly chat UI with IKNL branding, server-side citation rendering.

**What to do**:
1. Create `frontend/index.html` — single-page app calling `/agent/answer`
2. Create `frontend/css/styles.css` — IKNL green (`#00A67E`)
3. Create `frontend/js/app.js`:
   - Sends POST to `/agent/answer` with `{query, audience}`
   - Renders `answer_markdown` as HTML
   - Renders `citations` array as clickable links with source badges
   - Color-coded badges: kanker.nl=`#2196F3`, nkr-cijfers=`#4CAF50`, kankeratlas=`#FF9800`, richtlijnen=`#9C27B0`, publications=`#607D8B`
   - Feedback buttons per answer
   - Disclaimer footer
4. Mount static files in FastAPI: `app.mount("/app", StaticFiles(directory="../frontend"), name="frontend")`

**IMPORTANT**: Route prefix is `/app` not `/` to avoid shadowing existing API routes.

**Files to create**:
- `teams/uncloud-medical-grade-rag/frontend/index.html`
- `teams/uncloud-medical-grade-rag/frontend/css/styles.css`
- `teams/uncloud-medical-grade-rag/frontend/js/app.js`
- Modify `teams/uncloud-medical-grade-rag/backend/app/main.py` (mount static)

**Verification gate**:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3
curl -s http://localhost:8000/app/ | grep -q "KankerWijzer" && echo "FRONTEND LOADS: PASSED"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/app/css/styles.css | grep -q "200" && echo "CSS: PASSED"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/app/js/app.js | grep -q "200" && echo "JS: PASSED"
curl -s http://localhost:8000/health | grep -q "ok" && echo "API ROUTES NOT BROKEN: PASSED"
kill %1
```

**Ralph loop prompt**:
```
Build frontend at teams/uncloud-medical-grade-rag/frontend/. Chat UI calling /agent/answer, rendering answer_markdown and citations array as clickable source links with color badges. IKNL green #00A67E branding. Feedback buttons. Mount at /app in FastAPI. Output <promise>FRONTEND COMPLETE</promise> when: /app/ returns HTML with "KankerWijzer", CSS/JS return 200, and /health still works (no route shadowing).
```

---

### STEP 7: Lastmeter Integration (session-scoped, ephemeral)
**Goal**: Distress thermometer integrated into chat, NO persistent storage of sensitive scores.

**What to do**:
1. Create `frontend/js/lastmeter.js`:
   - Visual 0-10 thermometer slider
   - If score >= 4: show 5-domain problem checklist
   - Domains: Physical, Emotional, Practical, Social, Spiritual (39 items total)
   - Summary: radar chart + personalized kanker.nl resource links
   - **Consent banner**: "Deze gegevens worden niet opgeslagen. Ze worden alleen gebruikt om u relevante informatie te tonen."
   - **All assessment data stays client-side** (localStorage, cleared on session end)
   - Only sends problem domain keywords to backend for resource lookup
2. Create `backend/app/lastmeter.py`:
   - `POST /lastmeter/resources` — receives problem domain keywords (NOT raw scores), returns kanker.nl page URLs
   - Maps domain keywords → kanker.nl search queries → returns relevant page URLs from indexed data
   - **No storage** of assessment data. Stateless endpoint.
3. After assessment: chatbot's system prompt receives domain keywords to personalize follow-up responses

**Privacy design**:
- Raw thermometer scores and problem selections NEVER leave the browser
- Only anonymized domain keywords sent to backend ("physical:pain,fatigue" not "score:7,problems:[pijn,vermoeidheid,angst]")
- No session persistence server-side
- Consent banner required before assessment starts
- Client-side auto-clear on page close

**Files to create**:
- `teams/uncloud-medical-grade-rag/frontend/js/lastmeter.js`
- `teams/uncloud-medical-grade-rag/backend/app/lastmeter.py`
- Modify `teams/uncloud-medical-grade-rag/backend/app/main.py` (add lastmeter routes)

**Verification gate**:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3

# Test 1: Resource lookup works (no sensitive data sent)
curl -s http://localhost:8000/lastmeter/resources -X POST -H 'Content-Type: application/json' \
  -d '{"domains":["physical:pain","physical:fatigue","emotional:anxiety"]}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('resources') or isinstance(d, list), 'No resources'
print('LASTMETER RESOURCES PASSED')
"

# Test 2: No sensitive data storage endpoint exists (should NOT have /lastmeter/store or similar)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/lastmeter/store 2>/dev/null | python3 -c "
import sys; code=sys.stdin.read().strip()
assert code in ('404','405','422'), f'Unexpected: sensitive storage endpoint exists with code {code}'
print('NO SENSITIVE STORAGE: PASSED')
"

# Test 3: Frontend has Lastmeter with consent banner
curl -s http://localhost:8000/app/ | grep -qi "lastmeter" && echo "LASTMETER IN UI: PASSED"

kill %1
```

**Ralph loop prompt**:
```
Integrate Lastmeter at frontend/js/lastmeter.js and backend/app/lastmeter.py. Visual 0-10 slider, 5-domain problem checklist, radar chart summary. CRITICAL PRIVACY: raw scores stay client-side only. Only domain keywords sent to backend for resource lookup. Consent banner required. No persistent storage of assessment data. POST /lastmeter/resources receives domain keywords, returns kanker.nl page URLs. Output <promise>LASTMETER COMPLETE</promise> when: /lastmeter/resources returns resource links AND no /lastmeter/store endpoint exists AND frontend HTML contains "lastmeter".
```

---

### STEP 8: Neo4j Knowledge Graph (augmentation layer)
**Goal**: Build entity-relation graph from chunks in Neo4j. Augmentation only, never sole source.

**What to do**:
1. Create `backend/app/graphrag/` package
2. Create `backend/app/graphrag/schema.py` — entity/relation types
3. Create `backend/app/graphrag/extractor.py` — Claude Sonnet entity extraction from Dutch medical text
4. Create `backend/app/graphrag/builder.py` — process chunks from Postgres, insert entities/relations into Neo4j. Every node carries `sources: [citation_url1, ...]`
5. Create `backend/app/graphrag/retriever.py` — traverse 1-2 hops from query entity, return related entities with source URLs

**Scope limit**: Process the 87 cancer type overview pages (one per `kankersoort` in kanker.nl) + all PDF report/publication chunks (~350 chunks). Total: ~450 chunks. This provides broad cancer type coverage without claiming completeness.

**Augmentation-only rule (enforced in agent prompt)**:
> "The knowledge graph provides relationship context to help you understand connections between concepts. NEVER answer from graph data alone. Always cross-reference with vector-retrieved evidence from the primary sources. If the graph suggests a relationship but no supporting document chunk confirms it, do not include it in the answer."

**Files to create**:
- `teams/uncloud-medical-grade-rag/backend/app/graphrag/__init__.py`
- `teams/uncloud-medical-grade-rag/backend/app/graphrag/schema.py`
- `teams/uncloud-medical-grade-rag/backend/app/graphrag/extractor.py`
- `teams/uncloud-medical-grade-rag/backend/app/graphrag/builder.py`
- `teams/uncloud-medical-grade-rag/backend/app/graphrag/retriever.py`

**Verification gate**:
```bash
cd backend && ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY uv run python -m app.graphrag.builder
uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'medical-rag-password'))
with driver.session() as s:
    nodes = s.run('MATCH (n) RETURN count(n) as c').single()['c']
    edges = s.run('MATCH ()-[r]->() RETURN count(r) as c').single()['c']
    cancer_types = s.run('MATCH (n:CancerType) RETURN count(n) as c').single()['c']
    print(f'Nodes: {nodes}, Edges: {edges}, CancerTypes: {cancer_types}')
    assert nodes > 50, f'Expected >50 nodes'
    assert edges > 30, f'Expected >30 edges'
    assert cancer_types > 5, f'Expected >5 cancer types'
    # Verify provenance
    result = s.run('MATCH (n:CancerType) WHERE n.sources IS NOT NULL RETURN n.name, n.sources LIMIT 3')
    for r in result:
        print(f'  {r[\"n.name\"]}: {r[\"n.sources\"][:100]}')
        assert r['n.sources'], 'Missing sources on node'
print('GRAPH BUILD PASSED')
driver.close()
"
```

**Ralph loop prompt**:
```
Build Neo4j knowledge graph at backend/app/graphrag/. Extract entities (CancerType, Symptom, Treatment, Diagnostic, RiskFactor, BodyPart, Stage, Guideline) and relationships from ~450 chunks using Claude Sonnet. Insert into Neo4j. Every node must have sources property with citation URLs. This is an AUGMENTATION layer — never the sole source for answers. Output <promise>GRAPH COMPLETE</promise> when Neo4j has >50 nodes, >30 edges, >5 CancerType nodes with sources property.
```

---

### STEP 9: Wire Graph into Hybrid Retrieval
**Goal**: Agent can use graph for relationship exploration, but always cross-references with vector evidence.

**Modify**: `backend/app/agent/orchestrator.py` — wire the `explore_graph` tool to call `graphrag/retriever.py`

**Verification gate**:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3
curl -s http://localhost:8000/agent/answer -X POST -H 'Content-Type: application/json' \
  -d '{"query":"Welke behandelingen zijn er voor borstkanker?","audience":"patient"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('answer_markdown')
assert any(w in d['answer_markdown'].lower() for w in ['behandel','chemotherapie','operatie','bestraling'])
assert d.get('citations') and len(d['citations']) >= 1
# Citations must be from primary sources, not graph-only
for c in d['citations']:
    assert c.get('url'), 'Citation without URL'
print('GRAPH AUGMENTED ANSWER PASSED')
"
kill %1
```

**Ralph loop prompt**:
```
Wire Neo4j graph retriever into agent's explore_graph tool. The graph provides relationship context but answers MUST be cross-referenced with vector evidence. Output <promise>GRAPH WIRED</promise> when /agent/answer for "Welke behandelingen zijn er voor borstkanker?" returns answer with treatment info AND citations with URLs from primary sources.
```

---

### STEP 10: Crawl Remaining Sources (Firecrawl)
**Goal**: Crawl iknl.nl and richtlijnendatabase.nl, ingest into Postgres, project to Qdrant.

**What to do**:
1. Create `backend/app/ingestion/crawl_sources.py`:
   - Crawl iknl.nl/kankersoorten (~30 pages)
   - Crawl 5-10 richtlijnendatabase.nl guidelines
   - Use existing `firecrawl_client.py`
   - For each crawled page: create `SourceDocument` with full `Provenance`
   - Write to Postgres, then project to Qdrant
2. Requires `FIRECRAWL_API_KEY`

**Files to create**:
- `teams/uncloud-medical-grade-rag/backend/app/ingestion/crawl_sources.py`

**Verification gate**:
```bash
cd backend && uv run python -m app.ingestion.crawl_sources
uv run python -c "
from qdrant_client import QdrantClient
c = QdrantClient('localhost', port=6333)
info = c.get_collection('iknl_cancer_knowledge')
print(f'Total Qdrant points: {info.points_count}')
assert info.points_count > 6000
from app.vectorstore.qdrant_store import QdrantStore
store = QdrantStore()
results = store.search('IKNL kankersoorten', top_k=3)
iknl_hits = [r for r in results if 'iknl.nl' in r.get('citation_url','')]
print(f'IKNL hits: {len(iknl_hits)}')
print('CRAWL COMPLETE')
"
```

**Ralph loop prompt**:
```
Crawl iknl.nl/kankersoorten and richtlijnendatabase.nl guidelines using Firecrawl at backend/app/ingestion/crawl_sources.py. Create SourceDocument with full Provenance for each page. Write to Postgres, project to Qdrant. Output <promise>CRAWL COMPLETE</promise> when Qdrant has >6000 points and searching "IKNL kankersoorten" returns iknl.nl results.
```

---

### STEP 11: Feedback Collection
**Goal**: Structured user feedback stored in Postgres user_feedback table.

**What to do**:
1. Create `backend/app/feedback.py`:
   - `POST /feedback` — stores feedback in Postgres `user_feedback` table (already in schema)
   - `GET /feedback/stats` — returns aggregate stats
2. Wire frontend feedback buttons to `/feedback`

**Files to create/modify**:
- Create `teams/uncloud-medical-grade-rag/backend/app/feedback.py`
- Modify `teams/uncloud-medical-grade-rag/backend/app/main.py`
- Modify `teams/uncloud-medical-grade-rag/frontend/js/app.js`

**Verification gate**:
```bash
cd backend && uv run uvicorn app.main:app --port 8000 &
sleep 3
curl -s http://localhost:8000/feedback -X POST -H 'Content-Type: application/json' \
  -d '{"query_text":"test","answer_excerpt":"test","is_helpful":true,"notes":"goed antwoord"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('status') or d.get('feedback_id')
print('FEEDBACK PASSED')
"
kill %1
```

**Ralph loop prompt**:
```
Add feedback at backend/app/feedback.py. POST /feedback stores to Postgres user_feedback table (already in schema). GET /feedback/stats returns aggregates. Wire frontend buttons. Output <promise>FEEDBACK COMPLETE</promise> when POST /feedback returns success and data is in Postgres.
```

---

### STEP 12: Evaluation Pipeline (45 Questions)
**Goal**: Comprehensive medical QA evaluation with LLM-as-judge.

**What to do**:
1. Expand `backend/eval/golden_questions.yaml` to 45 questions
2. Update `backend/scripts/run_eval.py`:
   - For each question: call `/agent/answer`, check:
     - Deterministic: source whitelist compliance, citation count, refusal on unsafe
     - LLM-judge: faithfulness (claims supported by citations?), completeness
   - Write results to Postgres `evaluation_runs` + JSON report

**Question categories**:
- 10 patient info, 8 statistics, 6 geographic, 6 guideline, 5 cross-source, 5 ethical decline, 5 out-of-scope

**Verification gate**:
```bash
cd backend && uv run python scripts/run_eval.py
python3 -c "
import json
report = json.load(open('eval/results/eval_report.json'))
print(f'Total: {report[\"total\"]}, Passed: {report.get(\"passed\",0)}')
assert report['total'] >= 40
print('EVALUATION PASSED')
"
```

**Ralph loop prompt**:
```
Expand eval to 45 questions in backend/eval/golden_questions.yaml. Categories: patient info (10), statistics (8), geographic (6), guidelines (6), cross-source (5), ethical decline (5), out-of-scope (5). Update run_eval.py with source whitelist checks and LLM-as-judge faithfulness. Output <promise>EVAL COMPLETE</promise> when eval runs >=40 questions and generates eval_report.json.
```

---

### STEP 13: Final Polish & Docker Compose
**Goal**: One-command demo.

**Files to modify**: docker-compose.yml, README.md, .env.example

**Verification gate**:
```bash
docker compose up -d && sleep 20
curl -s http://localhost:8000/health | grep -q ok
curl -s http://localhost:8000/app/ | grep -q KankerWijzer
curl -s http://localhost:8000/agent/answer -X POST -H 'Content-Type: application/json' \
  -d '{"query":"Wat is borstkanker?"}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('answer_markdown') and d.get('citations')
print('E2E DEMO PASSED')
"
```

**Ralph loop prompt**:
```
Final polish: Dockerfile, docker-compose with all services, .env.example, README. Output <promise>DEMO READY</promise> when docker compose up starts everything and /agent/answer returns answers with citations.
```

---

## Implementation Order

```
STEP 1: Infrastructure
    │
STEP 2: Ingestion (Postgres-canonical, full Provenance)
    │
STEP 3: Qdrant Index (projection)
    │
STEP 4: Hybrid Retrieval (structured-first + vector)
    │
STEP 4.5: Medical-Grade Safety (abstention + red flags + source policy)
    │
STEP 5: Agent Upgrade (server-side citations, tool-calling)
    │
STEP 6: Frontend (chat + citations)
    │
STEP 7: Lastmeter (session-scoped, ephemeral)
    │
STEP 8: Neo4j Graph ──── STEP 9: Wire Graph (augmentation only)
STEP 10: Crawl Sources
STEP 11: Feedback
STEP 12: Evaluation (faithfulness, citation correctness, refusal accuracy, conflict tests)
STEP 13: Polish & Docker
```

**Critical path**: 1 → 2 → 3 → 4 → 4.5 → 5 → 6 → 7
**Parallel tracks**: 8→9, 10, 11, 12 (after Step 5)

---

## Hackathon Criteria Checklist

### Domain 1: Information Integrity / Correctness
| Criterion | How we satisfy it | Step |
|-----------|-------------------|------|
| Provides an answer | Agent with tool-calling returns answers from retrieved evidence | 5 |
| Show source provenance | Server-side `list[Provenance]` with clickable URLs, not LLM-authored | 2, 4, 5 |
| Only trusted IKNL sources | Source whitelist in `source_policy.py`, enforced at retrieval time | 4.5 |
| No inventing/distorting | Evidence-threshold abstention + source-only grounding in system prompt | 4.5, 5 |
| Declines when inaccurate | Score < 0.45 → refuse; missing evidence → refuse; conflict → hedge | 4, 4.5 |

### Domain 2: Usability
| Criterion | How we satisfy it | Step |
|-----------|-------------------|------|
| Better pathways for target groups | Audience-aware (patient/professional/policy) retrieval | 4, 5 |
| How people seek information | Conversational chat + Lastmeter distress assessment | 6, 7 |
| Fewer clicks / smarter navigation | Single question → multi-source answer with citations (vs visiting 7 websites) | 5, 6 |

### Domain 3: Ethics
| Criterion | How we satisfy it | Step |
|-----------|-------------------|------|
| Declines ethical issues | Red-flag routing (112, huisarts), treatment decision refusal, diagnosis refusal | 4.5 |

### Domain 4: Advanced Solution
| Criterion | How we satisfy it | Step |
|-----------|-------------------|------|
| Connects existing sources | All 7 sources ingested and searchable, structured-first for APIs | 2, 4, 10 |
| Improves context understanding | Knowledge graph augmentation + cross-source synthesis | 8, 9 |
| Potential for future IKNL use | Postgres-canonical, Provenance-first, Docker deploy, eval pipeline | All |

### Bonus: Feedback
| Criterion | How we satisfy it | Step |
|-----------|-------------------|------|
| User feedback on missing/unclear | Feedback buttons + Postgres storage + /feedback/stats | 11 |

---

## Environment Variables

```env
ANTHROPIC_API_KEY=sk-ant-...          # Required
FIRECRAWL_API_KEY=fc-...              # Required for Step 10
NEO4J_URI=bolt://localhost:7687       # Default
NEO4J_PASSWORD=medical-rag-password   # Default
QDRANT_URL=http://localhost:6333      # Default
POSTGRES_URL=postgresql://kankerwijzer:kankerwijzer@localhost:5432/kankerwijzer
```
