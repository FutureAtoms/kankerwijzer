"""GraphRAG retriever — query the Neo4j knowledge graph at retrieval time.

All Neo4j calls are wrapped in try/except so the system degrades gracefully
if Neo4j is empty or unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class GraphRetriever:
    """Query the Neo4j cancer knowledge graph."""

    def __init__(self, settings: Any) -> None:
        self._driver = None
        self._settings = settings
        if GraphDatabase is None:
            logger.info("GraphRetriever: neo4j dependency not installed — graph features disabled.")
            return
        try:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            self._driver.verify_connectivity()
            logger.info("GraphRetriever connected to Neo4j at %s", settings.neo4j_uri)
        except Exception as exc:
            logger.warning("GraphRetriever: Neo4j unavailable — graph features disabled. %s", exc)
            self._driver = None

    @property
    def available(self) -> bool:
        return self._driver is not None

    # ------------------------------------------------------------------
    # find_related — traverse up to max_hops from a given entity
    # ------------------------------------------------------------------

    def find_related(self, entity_name: str, max_hops: int = 2) -> dict:
        """Find entities related to the given entity within max_hops.

        Returns dict with entities, relationships, and source URLs.
        """
        if not self.available:
            return {"entities": [], "relationships": [], "sources": []}

        entity_lower = entity_name.strip().lower()

        cypher = """
        MATCH (start {name: $name})
        CALL apoc.path.subgraphAll(start, {maxLevel: $max_hops})
        YIELD nodes, relationships
        RETURN nodes, relationships
        """

        # Fallback to variable-length path if APOC is not available
        cypher_fallback = """
        MATCH path = (start {name: $name})-[*1..""" + str(max_hops) + """]->(end)
        WITH nodes(path) AS ns, relationships(path) AS rs
        UNWIND ns AS n
        WITH COLLECT(DISTINCT n) AS all_nodes, rs
        UNWIND rs AS r
        WITH all_nodes, COLLECT(DISTINCT r) AS all_rels
        RETURN all_nodes, all_rels
        """

        try:
            with self._driver.session() as session:
                # Try the variable-length path approach (no APOC dependency)
                result = session.run(
                    """
                    MATCH path = (start {name: $name})-[*1..%d]-(end)
                    WITH start,
                         COLLECT(DISTINCT end) AS related_nodes,
                         COLLECT(DISTINCT relationships(path)) AS all_rel_paths
                    RETURN start, related_nodes, all_rel_paths
                    """ % max_hops,
                    name=entity_lower,
                )

                record = result.single()
                if not record:
                    return {"entities": [], "relationships": [], "sources": []}

                # Process start node
                start_node = record["start"]
                entities = []
                sources = set()

                start_props = dict(start_node)
                start_labels = list(start_node.labels)
                entities.append({
                    "name": start_props.get("name", ""),
                    "type": start_labels[0] if start_labels else "Unknown",
                    "description": start_props.get("description", ""),
                })
                for s in start_props.get("sources", []):
                    if s:
                        sources.add(s)

                # Process related nodes
                for node in record["related_nodes"]:
                    props = dict(node)
                    labels = list(node.labels)
                    entities.append({
                        "name": props.get("name", ""),
                        "type": labels[0] if labels else "Unknown",
                        "description": props.get("description", ""),
                    })
                    for s in props.get("sources", []):
                        if s:
                            sources.add(s)

                # Process relationships
                relationships = []
                for rel_path in record["all_rel_paths"]:
                    for rel in rel_path:
                        relationships.append({
                            "type": rel.type,
                            "source": dict(rel.start_node).get("name", "") if hasattr(rel, "start_node") else "",
                            "target": dict(rel.end_node).get("name", "") if hasattr(rel, "end_node") else "",
                            "description": rel.get("description", "") if hasattr(rel, "get") else "",
                        })

                return {
                    "entities": entities[:50],  # cap
                    "relationships": relationships[:50],
                    "sources": list(sources)[:20],
                }

        except Exception as exc:
            logger.warning("find_related failed for '%s': %s", entity_name, exc)
            return {"entities": [], "relationships": [], "sources": []}

    # ------------------------------------------------------------------
    # get_cancer_type_info — get all known info about a cancer type
    # ------------------------------------------------------------------

    def get_cancer_type_info(self, cancer_type: str) -> dict:
        """Get all known info about a cancer type: treatments, symptoms, stages, sources."""
        if not self.available:
            return {"cancer_type": cancer_type, "treatments": [], "symptoms": [], "stages": [], "sources": []}

        ct_lower = cancer_type.strip().lower()

        try:
            with self._driver.session() as session:
                # Get treatments
                treatments_result = session.run(
                    """
                    MATCH (t:Treatment)-[:TREATS]->(c:CancerType {name: $name})
                    RETURN t.name AS name, t.description AS description, t.sources AS sources
                    """,
                    name=ct_lower,
                )
                treatments = []
                sources = set()
                for rec in treatments_result:
                    treatments.append({
                        "name": rec["name"],
                        "description": rec.get("description", ""),
                    })
                    for s in (rec.get("sources") or []):
                        if s:
                            sources.add(s)

                # Get symptoms
                symptoms_result = session.run(
                    """
                    MATCH (c:CancerType {name: $name})-[:CAUSES_SYMPTOM]->(s:Symptom)
                    RETURN s.name AS name, s.description AS description, s.sources AS sources
                    """,
                    name=ct_lower,
                )
                symptoms = []
                for rec in symptoms_result:
                    symptoms.append({
                        "name": rec["name"],
                        "description": rec.get("description", ""),
                    })
                    for s in (rec.get("sources") or []):
                        if s:
                            sources.add(s)

                # Get stages
                stages_result = session.run(
                    """
                    MATCH (c:CancerType {name: $name})-[:HAS_STAGE]->(st:Stage)
                    RETURN st.name AS name, st.description AS description, st.sources AS sources
                    """,
                    name=ct_lower,
                )
                stages = []
                for rec in stages_result:
                    stages.append({
                        "name": rec["name"],
                        "description": rec.get("description", ""),
                    })
                    for s in (rec.get("sources") or []):
                        if s:
                            sources.add(s)

                # Get the cancer type node itself for its sources
                ct_result = session.run(
                    "MATCH (c:CancerType {name: $name}) RETURN c.sources AS sources, c.description AS description",
                    name=ct_lower,
                )
                ct_rec = ct_result.single()
                ct_description = ""
                if ct_rec:
                    ct_description = ct_rec.get("description", "") or ""
                    for s in (ct_rec.get("sources") or []):
                        if s:
                            sources.add(s)

                return {
                    "cancer_type": ct_lower,
                    "description": ct_description,
                    "treatments": treatments,
                    "symptoms": symptoms,
                    "stages": stages,
                    "sources": list(sources)[:20],
                }

        except Exception as exc:
            logger.warning("get_cancer_type_info failed for '%s': %s", cancer_type, exc)
            return {"cancer_type": cancer_type, "treatments": [], "symptoms": [], "stages": [], "sources": []}

    # ------------------------------------------------------------------
    # search_entities — fuzzy search for entities
    # ------------------------------------------------------------------

    def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        """Fuzzy search for entities matching the query text."""
        if not self.available:
            return []

        q_lower = query.strip().lower()

        try:
            with self._driver.session() as session:
                # Use CONTAINS for fuzzy-ish matching
                result = session.run(
                    """
                    MATCH (n)
                    WHERE n.name IS NOT NULL AND n.name CONTAINS $search_term
                    RETURN n.name AS name, labels(n) AS types,
                           n.description AS description, n.sources AS sources
                    LIMIT $max_results
                    """,
                    search_term=q_lower,
                    max_results=limit,
                )

                entities = []
                for rec in result:
                    types = rec["types"]
                    entities.append({
                        "name": rec["name"],
                        "type": types[0] if types else "Unknown",
                        "description": rec.get("description", ""),
                        "sources": rec.get("sources", []) or [],
                    })

                return entities

        except Exception as exc:
            logger.warning("search_entities failed for '%s': %s", query, exc)
            return []

    # ------------------------------------------------------------------
    # graph_status — return node/edge counts
    # ------------------------------------------------------------------

    def graph_status(self) -> dict:
        """Return node count, edge count, and cancer types found."""
        if not self.available:
            return {
                "available": False,
                "node_count": 0,
                "edge_count": 0,
                "cancer_types": 0,
                "treatments": 0,
                "symptoms": 0,
                "stages": 0,
            }

        try:
            with self._driver.session() as session:
                nodes = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
                edges = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
                cancers = session.run("MATCH (n:CancerType) RETURN count(n) as c").single()["c"]
                treatments = session.run("MATCH (n:Treatment) RETURN count(n) as c").single()["c"]
                symptoms = session.run("MATCH (n:Symptom) RETURN count(n) as c").single()["c"]
                stages = session.run("MATCH (n:Stage) RETURN count(n) as c").single()["c"]

                # Get list of cancer type names
                cancer_names_result = session.run(
                    "MATCH (n:CancerType) RETURN n.name AS name ORDER BY n.name LIMIT 50"
                )
                cancer_names = [rec["name"] for rec in cancer_names_result]

                return {
                    "available": True,
                    "node_count": nodes,
                    "edge_count": edges,
                    "cancer_types": cancers,
                    "treatments": treatments,
                    "symptoms": symptoms,
                    "stages": stages,
                    "cancer_type_names": cancer_names,
                }

        except Exception as exc:
            logger.warning("graph_status failed: %s", exc)
            return {
                "available": False,
                "error": str(exc),
                "node_count": 0,
                "edge_count": 0,
                "cancer_types": 0,
            }

    # ------------------------------------------------------------------
    # get_full_graph — return all nodes and edges for visualization
    # ------------------------------------------------------------------

    def get_full_graph(self) -> dict:
        """Return all nodes and edges for D3 visualization."""
        if not self.available:
            return {"nodes": [], "links": []}

        try:
            with self._driver.session() as session:
                # Fetch all nodes
                node_result = session.run(
                    """
                    MATCH (n)
                    WHERE n.name IS NOT NULL
                    RETURN id(n) AS id, n.name AS name, labels(n) AS types,
                           n.description AS description, n.sources AS sources
                    """
                )
                nodes = []
                node_id_map = {}  # neo4j internal id -> our id
                for rec in node_result:
                    neo_id = rec["id"]
                    types = rec["types"]
                    node_type = types[0] if types else "Unknown"
                    node_id = f"{node_type.lower()}-{rec['name']}"
                    node_id_map[neo_id] = node_id
                    nodes.append({
                        "id": node_id,
                        "type": node_type,
                        "label": rec["name"],
                        "data": {
                            "name": rec["name"],
                            "description": rec.get("description") or "",
                            "sources": rec.get("sources") or [],
                        },
                    })

                # Fetch all relationships
                rel_result = session.run(
                    """
                    MATCH (a)-[r]->(b)
                    WHERE a.name IS NOT NULL AND b.name IS NOT NULL
                    RETURN id(a) AS source_id, id(b) AS target_id,
                           type(r) AS rel_type, r.description AS description
                    """
                )
                links = []
                seen_links = set()
                for rec in rel_result:
                    source = node_id_map.get(rec["source_id"])
                    target = node_id_map.get(rec["target_id"])
                    if source and target:
                        link_key = f"{source}-{rec['rel_type']}-{target}"
                        if link_key not in seen_links:
                            seen_links.add(link_key)
                            links.append({
                                "source": source,
                                "target": target,
                                "rel": rec["rel_type"],
                            })

                return {"nodes": nodes, "links": links}

        except Exception as exc:
            logger.warning("get_full_graph failed: %s", exc)
            return {"nodes": [], "links": []}

    def close(self) -> None:
        if self._driver:
            self._driver.close()
