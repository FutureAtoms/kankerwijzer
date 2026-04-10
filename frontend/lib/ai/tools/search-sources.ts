import { tool } from "ai";
import { z } from "zod";
import { getDriver } from "@/lib/db/driver";

/**
 * Search trusted cancer information sources (kanker.nl) using Neo4j full-text search.
 * Returns exact text chunks with source URLs — the AI must quote these verbatim.
 */
export const searchSources = tool({
  description: `Search the trusted kanker.nl knowledge base for cancer information.
ALWAYS use this tool FIRST before answering any question about cancer types, symptoms, treatments, side effects, or patient information.
This searches 2816 pages from kanker.nl (the official Dutch cancer patient information website maintained by KWF/IKNL).

The results contain EXACT text from the source. You MUST:
1. Quote the returned text EXACTLY as-is (do not paraphrase or modify)
2. Always include the source URL as a citation
3. If no results are found, say so — do NOT make up information

You can search in Dutch or English terms. The content is in Dutch.`,
  inputSchema: z.object({
    query: z
      .string()
      .describe(
        "Search query — use Dutch medical terms for best results (e.g. 'borstkanker behandeling', 'longkanker symptomen', 'chemotherapie bijwerkingen')"
      ),
    cancerType: z
      .string()
      .optional()
      .describe(
        "Optional: filter by cancer type slug (e.g. 'borstkanker', 'longkanker', 'darmkanker-dikkedarmkanker')"
      ),
    limit: z
      .number()
      .optional()
      .default(5)
      .describe("Number of results to return (default: 5, max: 10)"),
  }),
  execute: async (input) => {
    const driver = getDriver();
    const session = driver.session();

    try {
      const maxResults = Math.min(input.limit ?? 5, 10);

      // Escape special Lucene characters in the query
      const escapedQuery = input.query
        .replace(/[+\-&|!(){}[\]^"~*?:\\/]/g, "\\$&")
        .trim();

      if (!escapedQuery) {
        return {
          error: "Please provide a search query.",
        };
      }

      let cypher: string;
      let params: Record<string, unknown>;

      if (input.cancerType) {
        cypher = `
          CALL db.index.fulltext.queryNodes("chunk_fulltext", $query)
          YIELD node, score
          WHERE node.cancerType CONTAINS $cancerType
          RETURN node.url AS url, node.text AS text, node.cancerType AS cancerType, score
          LIMIT $limit
        `;
        params = { query: escapedQuery, cancerType: input.cancerType, limit: maxResults };
      } else {
        cypher = `
          CALL db.index.fulltext.queryNodes("chunk_fulltext", $query)
          YIELD node, score
          RETURN node.url AS url, node.text AS text, node.cancerType AS cancerType, score
          LIMIT $limit
        `;
        params = { query: escapedQuery, limit: maxResults };
      }

      const result = await session.run(cypher, params);

      const sources = result.records.map((r) => ({
        url: r.get("url") as string,
        text: r.get("text") as string,
        cancerType: r.get("cancerType") as string,
        relevanceScore: r.get("score") as number,
      }));

      if (sources.length === 0) {
        return {
          source: "kanker.nl",
          query: input.query,
          results: [],
          message: "No matching content found. Try different search terms (in Dutch).",
        };
      }

      return {
        source: "kanker.nl",
        query: input.query,
        resultCount: sources.length,
        results: sources.map((s) => ({
          url: s.url,
          exactText: s.text,
          cancerType: s.cancerType,
          relevanceScore: Math.round(s.relevanceScore * 100) / 100,
        })),
        instruction:
          "IMPORTANT: Quote the 'exactText' field verbatim in your response. Do NOT paraphrase. Always cite the URL.",
      };
    } catch (error) {
      return {
        error: `Search failed: ${error instanceof Error ? error.message : "Unknown error"}`,
        suggestion: "Try simpler search terms in Dutch.",
      };
    } finally {
      await session.close();
    }
  },
});
