import { tool } from "ai";
import { z } from "zod";

// Cancer Atlas API — Regional cancer incidence data
// Docs: https://kankeratlas.iknl.nl

const ATLAS_API = "https://iknl-atlas-strapi-prod.azurewebsites.net/api";
const ATLAS_FILTERS =
  "https://kankeratlas.iknl.nl/locales/nl/filters.json?format=json";

async function fetchJsonGet(url: string) {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Cancer Atlas API returned ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

async function fetchFilters() {
  return fetchJsonGet(ATLAS_FILTERS);
}

async function fetchCancerGroups() {
  return fetchJsonGet(`${ATLAS_API}/cancer-groups/cancergrppc?locale=nl`);
}

async function fetchPostcodeInfo(digits: number) {
  return fetchJsonGet(`${ATLAS_API}/postcodes/getbypc/${digits}`);
}

async function fetchCancerData(
  cancerGroup: number,
  sex: number,
  postcode: number
) {
  return fetchJsonGet(
    `${ATLAS_API}/cancer-datas/getbygroupsexpostcode/${cancerGroup}/${sex}/${postcode}`
  );
}

export const getCancerAtlasData = tool({
  description: `Query the IKNL Cancer Atlas for regional cancer incidence data across the Netherlands.
Use this tool when the user asks about cancer rates in a specific region, postal code area, or geographic variation.
The Cancer Atlas shows how cancer incidence in a region compares to the Dutch national average.

Actions:
- "list-filters": Get available cancer types and filter options
- "list-cancer-groups": Get all cancer group IDs and names
- "postcode-info": Get information about a 3-digit postal code area
- "query": Get cancer incidence data for a specific cancer group, sex, and postal code

Common cancer group IDs: 11 = lung cancer, 1 = breast cancer, 6 = colorectal cancer, 14 = prostate cancer.
Sex codes: 1 = male, 2 = female, 3 = all.
Postcode: first 3 digits of Dutch postal code (e.g., 103 for Amsterdam North).

The result includes a "p50" value which indicates the ratio compared to the national average.
For example, p50=1.46 means 46% above the national average; p50=0.85 means 15% below.`,
  inputSchema: z.object({
    action: z
      .enum(["list-filters", "list-cancer-groups", "postcode-info", "query"])
      .describe("Action to perform"),
    cancerGroup: z
      .number()
      .optional()
      .describe(
        "Cancer group ID (e.g., 11 for lung cancer, 1 for breast cancer)"
      ),
    sex: z
      .number()
      .optional()
      .describe("Sex code: 1 = male, 2 = female, 3 = all"),
    postcode: z
      .number()
      .optional()
      .describe(
        "First 3 digits of Dutch postal code (e.g., 103 for Amsterdam North)"
      ),
  }),
  execute: async (input) => {
    try {
      if (input.action === "list-filters") {
        const filters = await fetchFilters();
        return {
          source: "kankeratlas.iknl.nl",
          description: "Available filters for the Cancer Atlas",
          data: filters,
        };
      }

      if (input.action === "list-cancer-groups") {
        const groups = await fetchCancerGroups();
        return {
          source: "kankeratlas.iknl.nl",
          description: "Available cancer groups with their IDs",
          data: groups,
        };
      }

      if (input.action === "postcode-info") {
        if (input.postcode === undefined) {
          return {
            error:
              "Please provide a 3-digit postcode to look up area information.",
          };
        }
        const info = await fetchPostcodeInfo(input.postcode);
        return {
          source: "kankeratlas.iknl.nl",
          postcode: input.postcode,
          data: info,
        };
      }

      // action === "query"
      if (
        input.cancerGroup === undefined ||
        input.sex === undefined ||
        input.postcode === undefined
      ) {
        return {
          error:
            "Please provide cancerGroup, sex, and postcode to query cancer atlas data. Use 'list-cancer-groups' to find the right cancer group ID.",
        };
      }

      const data = await fetchCancerData(
        input.cancerGroup,
        input.sex,
        input.postcode
      );

      return {
        source: "kankeratlas.iknl.nl",
        description: `Cancer incidence data for cancer group ${input.cancerGroup}, sex ${input.sex}, postcode area ${input.postcode}. The p50 value shows the ratio compared to the national average (1.0 = average, >1 = above average, <1 = below average).`,
        filters: {
          cancerGroup: input.cancerGroup,
          sex: input.sex,
          postcode: input.postcode,
        },
        data,
      };
    } catch (error) {
      return {
        error: `Failed to fetch Cancer Atlas data: ${error instanceof Error ? error.message : "Unknown error"}`,
        suggestion:
          "Try using action 'list-cancer-groups' to see available cancer types, or check the postcode.",
      };
    }
  },
});
