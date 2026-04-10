CREATE CONSTRAINT source_id_unique IF NOT EXISTS
FOR (s:Source) REQUIRE s.source_id IS UNIQUE;

CREATE CONSTRAINT document_id_unique IF NOT EXISTS
FOR (d:Document) REQUIRE d.document_id IS UNIQUE;

CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;

CREATE CONSTRAINT cancer_type_name_unique IF NOT EXISTS
FOR (c:CancerType) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT treatment_name_unique IF NOT EXISTS
FOR (t:Treatment) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT symptom_name_unique IF NOT EXISTS
FOR (s:Symptom) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT region_code_unique IF NOT EXISTS
FOR (r:Region) REQUIRE r.code IS UNIQUE;

CREATE INDEX chunk_title_idx IF NOT EXISTS
FOR (c:Chunk) ON (c.section);

// Expected labels
// (:Source {source_id, name, publisher})
// (:Document {document_id, title, canonical_url, content_type})
// (:Chunk {chunk_id, chunk_text, page_number, section, citation_url})
// (:CancerType {name})
// (:Treatment {name})
// (:Symptom {name})
// (:Stage {name})
// (:Region {code, postcode_digits})
// (:Audience {name})
// (:Publication {title})
//
// Expected relationships
// (:Source)-[:PUBLISHES]->(:Document)
// (:Document)-[:HAS_CHUNK]->(:Chunk)
// (:Chunk)-[:MENTIONS_CANCER_TYPE]->(:CancerType)
// (:Chunk)-[:MENTIONS_TREATMENT]->(:Treatment)
// (:Chunk)-[:MENTIONS_SYMPTOM]->(:Symptom)
// (:Chunk)-[:MENTIONS_STAGE]->(:Stage)
// (:Chunk)-[:MENTIONS_REGION]->(:Region)
// (:Chunk)-[:RELEVANT_TO]->(:Audience)
// (:Publication)-[:SUPPORTS]->(:CancerType)
