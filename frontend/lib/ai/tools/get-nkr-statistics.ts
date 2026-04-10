import { tool } from "ai";
import { z } from "zod";

// NKR Cijfers API — Netherlands Cancer Registry statistics
// Docs: https://nkr-cijfers.iknl.nl

const NKR_API = "https://api.nkr-cijfers.iknl.nl/api";

async function fetchJson(endpoint: string, body: Record<string, unknown>) {
  const res = await fetch(`${NKR_API}/${endpoint}?format=json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`NKR API ${endpoint} returned ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

export const getNkrStatistics = tool({
  description: `Query the Netherlands Cancer Registry (NKR) for cancer statistics.
Use this tool when the user asks about cancer incidence, prevalence, survival rates, stage distribution, or trends in the Netherlands.

Available actions:
- "list-topics": Get all available navigation items (topics)
- "get-config": Get the configuration for a specific topic (shows required groupBy, available statistics)
- "list-filters": Get available filter options for a specific topic
- "query": Fetch actual data for a topic

IMPORTANT: Before querying data, first use "get-config" to understand what groupBy and statistic are needed.

Common navigation codes:
- "incidentie/periode" — Incidence over time (groupBy: filter/periode-van-diagnose)
- "incidentie/verdeling-per-stadium" — Stage distribution (groupBy: filter/stadium)
- "prevalentie/periode" — Prevalence over time
- "sterfte/periode" — Mortality over time
- "overleving/periode" — Relative survival

Common cancer type codes: "kankersoort/totaal/alle" (all), "kankersoort/borstkanker" (breast), "kankersoort/longkanker" (lung), "kankersoort/darmkanker" (colorectal), "kankersoort/prostaatkanker" (prostate).`,
  inputSchema: z.object({
    action: z
      .enum(["list-topics", "get-config", "list-filters", "query"])
      .describe("Action to perform"),
    navigationCode: z
      .string()
      .optional()
      .describe('Navigation code for the topic, e.g. "incidentie/verdeling-per-stadium"'),
    cancerType: z
      .string()
      .optional()
      .describe('Cancer type code, e.g. "kankersoort/totaal/alle"'),
    period: z
      .string()
      .optional()
      .describe('Period code, e.g. "periode/1-jaar/2024"'),
    sex: z
      .string()
      .optional()
      .describe('Sex filter, e.g. "geslacht/totaal/alle", "geslacht/man", "geslacht/vrouw"'),
    ageGroup: z
      .string()
      .optional()
      .describe('Age group, e.g. "leeftijdsgroep/totaal/alle"'),
    region: z
      .string()
      .optional()
      .describe('Region, e.g. "regio/totaal/alle"'),
  }),
  execute: async (input) => {
    try {
      // --- list-topics ---
      if (input.action === "list-topics") {
        const items = await fetchJson("navigation-items", { language: "nl-NL" });
        return {
          source: "nkr-cijfers.iknl.nl",
          description: "Available topics from the Netherlands Cancer Registry",
          data: items,
        };
      }

      if (!input.navigationCode) {
        return {
          error: "Please provide a navigationCode. Use action 'list-topics' first to see available options.",
        };
      }

      // --- get-config ---
      if (input.action === "get-config") {
        const config = await fetchJson("configuration", {
          language: "nl-NL",
          currentNavigation: { code: input.navigationCode },
        });
        return {
          source: "nkr-cijfers.iknl.nl",
          topic: input.navigationCode,
          description: `Configuration for ${input.navigationCode}. The 'groupBy' field shows what must be used as groupBy in a data query.`,
          data: config,
        };
      }

      // --- list-filters ---
      if (input.action === "list-filters") {
        const filters = await fetchJson("filter-groups", {
          currentNavigation: { code: input.navigationCode },
          language: "nl-NL",
          filterValuesSelected: [],
          userAction: { code: "restart", value: "" },
        });
        return {
          source: "nkr-cijfers.iknl.nl",
          topic: input.navigationCode,
          description: `Available filters for topic: ${input.navigationCode}`,
          data: filters,
        };
      }

      // --- query ---
      // First get the configuration to know the correct groupBy
      const config = await fetchJson("configuration", {
        language: "nl-NL",
        currentNavigation: { code: input.navigationCode },
      });

      const configGroupBy: { code: string }[] = config.groupBy ?? [];

      // Build groupBy from configuration
      const groupBy: Record<string, unknown>[] = [];
      for (const gb of configGroupBy) {
        if (gb.code === "filter/periode-van-diagnose") {
          // For period-based groupBy, we need period values
          // Fetch filter groups to get available periods
          const filters = await fetchJson("filter-groups", {
            currentNavigation: { code: input.navigationCode },
            language: "nl-NL",
            filterValuesSelected: [],
            userAction: { code: "restart", value: "" },
          });
          const periodFilter = (filters as { code: string; values: { code: string }[] }[])
            .find((f: { code: string }) => f.code === "filter/periode-van-diagnose");
          const periodValues = periodFilter?.values?.slice(0, 10) ?? [
            { code: "periode/1-jaar/2024" },
          ];
          groupBy.push({ code: gb.code, values: periodValues.map((v: { code: string }) => ({ code: v.code })) });
        } else if (gb.code === "filter/stadium") {
          groupBy.push({
            code: gb.code,
            values: [
              { code: "stadium/0" },
              { code: "stadium/i" },
              { code: "stadium/ii" },
              { code: "stadium/iii" },
              { code: "stadium/iv" },
              { code: "stadium/x" },
              { code: "stadium/nvt" },
            ],
          });
        } else if (gb.code === "filter/jaren-na-diagnose") {
          groupBy.push({
            code: gb.code,
            values: [
              { code: "jaren-na-diagnose/1" },
              { code: "jaren-na-diagnose/3" },
              { code: "jaren-na-diagnose/5" },
              { code: "jaren-na-diagnose/10" },
            ],
          });
        } else {
          // For unknown groupBy, fetch filter values
          const filters = await fetchJson("filter-groups", {
            currentNavigation: { code: input.navigationCode },
            language: "nl-NL",
            filterValuesSelected: [],
            userAction: { code: "restart", value: "" },
          });
          const filterGroup = (filters as { code: string; values: { code: string }[] }[])
            .find((f: { code: string }) => f.code === gb.code);
          if (filterGroup?.values) {
            groupBy.push({
              code: gb.code,
              values: filterGroup.values.slice(0, 10).map((v: { code: string }) => ({ code: v.code })),
            });
          }
        }
      }

      // Build aggregateBy — exclude any filter that's already in groupBy
      const groupByCodes = new Set(configGroupBy.map((g) => g.code));
      const aggregateBy: Record<string, unknown>[] = [];

      if (!groupByCodes.has("filter/kankersoort")) {
        aggregateBy.push({
          code: "filter/kankersoort",
          values: [{ code: input.cancerType ?? "kankersoort/totaal/alle" }],
        });
      }
      if (!groupByCodes.has("filter/periode-van-diagnose")) {
        aggregateBy.push({
          code: "filter/periode-van-diagnose",
          values: [{ code: input.period ?? "periode/1-jaar/2024" }],
        });
      }
      if (!groupByCodes.has("filter/geslacht")) {
        aggregateBy.push({
          code: "filter/geslacht",
          values: [{ code: input.sex ?? "geslacht/totaal/alle" }],
        });
      }
      if (!groupByCodes.has("filter/leeftijdsgroep")) {
        aggregateBy.push({
          code: "filter/leeftijdsgroep",
          values: [{ code: input.ageGroup ?? "leeftijdsgroep/totaal/alle" }],
        });
      }
      if (!groupByCodes.has("filter/regio")) {
        aggregateBy.push({
          code: "filter/regio",
          values: [{ code: input.region ?? "regio/totaal/alle" }],
        });
      }

      // Determine statistic based on navigation code
      const isDistribution = input.navigationCode.includes("verdeling");
      const isOverleving = input.navigationCode.includes("overleving");
      let statisticCode = "statistiek/aantallen";
      if (isDistribution) {
        statisticCode = "statistiek/verdeling";
      } else if (isOverleving) {
        statisticCode = "statistiek/relatieve-overleving";
      }

      const body: Record<string, unknown> = {
        language: "nl-NL",
        navigation: { code: input.navigationCode },
        groupBy,
        aggregateBy,
        statistic: { code: statisticCode },
      };

      const data = await fetchJson("data", body);
      return {
        source: "nkr-cijfers.iknl.nl",
        topic: input.navigationCode,
        filters: {
          cancerType: input.cancerType ?? "kankersoort/totaal/alle",
          period: input.period ?? "periode/1-jaar/2024",
          sex: input.sex ?? "geslacht/totaal/alle",
        },
        data,
      };
    } catch (error) {
      return {
        error: `Failed to fetch NKR data: ${error instanceof Error ? error.message : "Unknown error"}`,
        suggestion:
          "Try using action 'list-topics' to see available options, then 'get-config' to understand the required query structure.",
      };
    }
  },
});
