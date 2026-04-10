"""Build the Neo4j knowledge graph from chunks stored in Postgres.

Run via:
    uv run python -m app.graphrag.builder

Strategy:
  1. Read the top 100 longest chunks from Postgres (most information-dense).
  2. For each chunk, call Claude Sonnet to extract entities and relationships.
  3. Insert nodes and edges into Neo4j following the schema in neo4j_schema.cypher.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://kankerwijzer:kankerwijzer@localhost:5432/kankerwijzer",
)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "medical-rag-password")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

EXTRACTION_MODEL = "claude-sonnet-4-6"
MAX_CHUNKS = 100  # hackathon limit
MIN_CHUNK_LEN = 100
BATCH_SIZE = 5  # chunks per API call

# ---------------------------------------------------------------------------
# Entity extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
Analyseer de volgende teksten over kanker en extraheer medische entiteiten en relaties.

{chunks_block}

Geef JSON terug met ALLE entiteiten en relaties uit ALLE bovenstaande teksten.
Elk entity moet een uniek name hebben (lowercase Nederlands).
Geldige entity types: CancerType, Treatment, Symptom, Stage
Geldige relation types: TREATS, CAUSES_SYMPTOM, HAS_STAGE, DIAGNOSED_BY

BELANGRIJK: Houd descriptions KORT (max 15 woorden). Maximaal 20 entities en 20 relaties.
Antwoord ALLEEN met geldige JSON, geen uitleg of markdown:
{{
  "entities": [
    {{"name": "...", "type": "CancerType|Treatment|Symptom|Stage", "description": "korte beschrijving", "source_url": "..."}}
  ],
  "relations": [
    {{"source": "...", "target": "...", "type": "TREATS|CAUSES_SYMPTOM|HAS_STAGE|DIAGNOSED_BY", "description": "kort"}}
  ]
}}"""


# ---------------------------------------------------------------------------
# Fetch chunks from Postgres
# ---------------------------------------------------------------------------

def fetch_top_chunks(postgres_url: str, limit: int = MAX_CHUNKS) -> list[dict]:
    """Fetch the longest chunks from Postgres, joined with document metadata."""
    sql = """
        SELECT c.chunk_id, c.chunk_text, c.citation_url, c.section,
               c.page_number, c.document_id,
               d.title AS doc_title, d.content_type,
               s.name AS source_name, s.publisher
        FROM chunks c
        JOIN documents d ON c.document_id = d.document_id
        JOIN source_catalog s ON d.source_id = s.source_id
        WHERE length(c.chunk_text) >= %s
        ORDER BY length(c.chunk_text) DESC
        LIMIT %s
    """
    with psycopg.connect(postgres_url, row_factory=dict_row) as conn:
        rows = conn.execute(sql, (MIN_CHUNK_LEN, limit)).fetchall()
    logger.info("Fetched %d chunks from Postgres (min length %d chars)", len(rows), MIN_CHUNK_LEN)
    return rows


# ---------------------------------------------------------------------------
# Claude Sonnet entity extraction
# ---------------------------------------------------------------------------

def extract_entities_batch(chunks: list[dict], api_key: str) -> dict:
    """Call Claude Sonnet to extract entities and relations from a batch of chunks."""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    # Build the chunks block
    parts = []
    for i, chunk in enumerate(chunks, 1):
        url = chunk.get("citation_url", "onbekend")
        text = chunk["chunk_text"][:1200]  # limit per chunk to control token usage and output size
        parts.append(f"--- Tekst {i} ---\nBron: {url}\n{text}\n")

    chunks_block = "\n".join(parts)
    prompt = EXTRACTION_PROMPT.format(chunks_block=chunks_block)

    try:
        response = client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=8192,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Try to parse JSON - handle markdown code blocks
        if raw.startswith("```"):
            # Remove markdown code block wrapping
            lines = raw.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            raw = "\n".join(json_lines)

        result = json.loads(raw)
        return result
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse JSON from Claude response: %s", exc)
        return {"entities": [], "relations": []}
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc)
        return {"entities": [], "relations": []}


# ---------------------------------------------------------------------------
# Neo4j graph population
# ---------------------------------------------------------------------------

def apply_schema(driver, schema_path: str | Path) -> None:
    """Apply the Neo4j schema constraints from the cypher file."""
    schema_file = Path(schema_path)
    if not schema_file.exists():
        logger.warning("Schema file not found at %s — skipping constraints", schema_path)
        return

    cypher = schema_file.read_text()
    with driver.session() as session:
        for stmt in cypher.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("//"):
                try:
                    session.run(stmt)
                    logger.info("Applied: %s", stmt[:60])
                except Exception as exc:
                    # Constraints may already exist — that's fine
                    logger.debug("Schema statement skipped (may already exist): %s", exc)
    logger.info("Schema applied.")


def normalize_name(name: str) -> str:
    """Normalize entity name to lowercase Dutch."""
    return name.strip().lower()


def insert_entities_and_relations(
    driver, extraction: dict, source_urls: list[str]
) -> tuple[int, int]:
    """Insert extracted entities and relations into Neo4j. Returns (nodes_created, rels_created)."""
    entities = extraction.get("entities", [])
    relations = extraction.get("relations", [])

    nodes_created = 0
    rels_created = 0

    valid_types = {"CancerType", "Treatment", "Symptom", "Stage"}
    valid_rel_types = {"TREATS", "CAUSES_SYMPTOM", "HAS_STAGE", "DIAGNOSED_BY"}

    with driver.session() as session:
        # Insert entities
        for ent in entities:
            ent_type = ent.get("type", "")
            if ent_type not in valid_types:
                continue
            name = normalize_name(ent.get("name", ""))
            if not name:
                continue
            description = ent.get("description", "")
            source_url = ent.get("source_url", "")

            # Collect all source URLs for this entity
            sources = [u for u in [source_url] + source_urls if u]
            sources = list(set(sources))[:10]  # deduplicate, cap at 10

            cypher = f"""
            MERGE (n:{ent_type} {{name: $name}})
            ON CREATE SET n.description = $description, n.sources = $sources
            ON MATCH SET n.description = CASE WHEN size(n.description) < size($description)
                THEN $description ELSE n.description END,
                n.sources = [x IN n.sources + $sources WHERE x <> '' | x][..10]
            """
            try:
                session.run(cypher, name=name, description=description, sources=sources)
                nodes_created += 1
            except Exception as exc:
                logger.debug("Entity insert failed for %s: %s", name, exc)

        # Insert relations
        for rel in relations:
            rel_type = rel.get("type", "")
            if rel_type not in valid_rel_types:
                continue
            source_name = normalize_name(rel.get("source", ""))
            target_name = normalize_name(rel.get("target", ""))
            description = rel.get("description", "")
            if not source_name or not target_name:
                continue

            # We need to find the entity types for source and target
            # Use a generic approach — match any label
            cypher = f"""
            MATCH (a {{name: $source_name}})
            MATCH (b {{name: $target_name}})
            MERGE (a)-[r:{rel_type}]->(b)
            ON CREATE SET r.description = $description
            """
            try:
                session.run(cypher, source_name=source_name, target_name=target_name, description=description)
                rels_created += 1
            except Exception as exc:
                logger.debug("Relation insert failed %s->%s: %s", source_name, target_name, exc)

    return nodes_created, rels_created


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_graph() -> None:
    """Main entry point: read chunks from Postgres, extract entities, insert into Neo4j."""
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set. Provide it via environment variable.")
        sys.exit(1)

    # 1. Connect to Neo4j and apply schema
    logger.info("Connecting to Neo4j at %s ...", NEO4J_URI)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        logger.info("Neo4j connection OK.")
    except Exception as exc:
        logger.error("Cannot connect to Neo4j: %s", exc)
        sys.exit(1)

    schema_path = Path(__file__).resolve().parents[1] / "storage" / "neo4j_schema.cypher"
    apply_schema(driver, schema_path)

    # 2. Fetch chunks from Postgres
    logger.info("Fetching top %d chunks from Postgres ...", MAX_CHUNKS)
    chunks = fetch_top_chunks(POSTGRES_URL, limit=MAX_CHUNKS)
    if not chunks:
        logger.warning("No chunks found in Postgres. Nothing to index.")
        driver.close()
        return

    # 3. Process in batches
    total_nodes = 0
    total_rels = 0
    total_chunks = len(chunks)
    batch_count = 0

    for i in range(0, total_chunks, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        batch_count += 1

        # Collect source URLs from this batch
        source_urls = [c.get("citation_url", "") for c in batch if c.get("citation_url")]

        # Extract entities using Claude Sonnet
        extraction = extract_entities_batch(batch, ANTHROPIC_API_KEY)

        ent_count = len(extraction.get("entities", []))
        rel_count = len(extraction.get("relations", []))

        # Insert into Neo4j
        nodes, rels = insert_entities_and_relations(driver, extraction, source_urls)
        total_nodes += nodes
        total_rels += rels

        # Progress
        processed = min(i + BATCH_SIZE, total_chunks)
        if processed % 10 == 0 or processed == total_chunks:
            logger.info(
                "Progress: %d/%d chunks | batch %d extracted %d entities, %d relations | "
                "total nodes=%d, rels=%d",
                processed, total_chunks, batch_count, ent_count, rel_count,
                total_nodes, total_rels,
            )

        # Small delay to respect rate limits
        time.sleep(0.5)

    # 4. Print final summary
    with driver.session() as session:
        node_count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
        edge_count = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        cancer_count = session.run("MATCH (n:CancerType) RETURN count(n) as c").single()["c"]

    logger.info(
        "Graph build complete. Nodes: %d, Edges: %d, CancerTypes: %d",
        node_count, edge_count, cancer_count,
    )

    driver.close()
    logger.info("Done.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    build_graph()
