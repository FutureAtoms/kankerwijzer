export const DEFAULT_CHAT_MODEL = "claude-sonnet-4-20250514";

export const titleModel = {
  id: "claude-sonnet-4-20250514",
  name: "Claude Sonnet 4",
  provider: "anthropic",
  description: "Fast model for title generation",
};

export type ModelCapabilities = {
  tools: boolean;
  vision: boolean;
  reasoning: boolean;
};

export type ChatModel = {
  id: string;
  name: string;
  provider: string;
  description: string;
  gatewayOrder?: string[];
  reasoningEffort?: "none" | "minimal" | "low" | "medium" | "high";
};

export const chatModels: ChatModel[] = [
  {
    id: "claude-sonnet-4-20250514",
    name: "Claude Sonnet 4",
    provider: "anthropic",
    description: "Fast, intelligent model with tool use and vision",
  },
  {
    id: "claude-haiku-3-5-20241022",
    name: "Claude 3.5 Haiku",
    provider: "anthropic",
    description: "Fastest Anthropic model, great for quick tasks",
  },
];

export async function getCapabilities(): Promise<
  Record<string, ModelCapabilities>
> {
  // Anthropic models: all support tools and vision, none are "reasoning" models
  const results: Record<string, ModelCapabilities> = {};
  for (const model of chatModels) {
    results[model.id] = {
      tools: true,
      vision: true,
      reasoning: false,
    };
  }
  return results;
}

export const isDemo = process.env.IS_DEMO === "1";

type GatewayModel = {
  id: string;
  name: string;
  type?: string;
  tags?: string[];
};

export type GatewayModelWithCapabilities = ChatModel & {
  capabilities: ModelCapabilities;
};

export async function getAllGatewayModels(): Promise<
  GatewayModelWithCapabilities[]
> {
  // Not using gateway anymore — return our Anthropic models directly
  return chatModels.map((m) => ({
    ...m,
    capabilities: { tools: true, vision: true, reasoning: false },
  }));
}

export function getActiveModels(): ChatModel[] {
  return chatModels;
}

export const allowedModelIds = new Set(chatModels.map((m) => m.id));

export const modelsByProvider = chatModels.reduce(
  (acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  },
  {} as Record<string, ChatModel[]>
);
