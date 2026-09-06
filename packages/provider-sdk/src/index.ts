export type Capability = "streaming" | "tools" | "reasoning" | "vision" | "files" | "webSearch" | "conversations";

export type ProviderCapabilities = Readonly<Record<Capability, boolean>>;

export type MessageRole = "system" | "user" | "assistant" | "tool";

export interface WagentMessage {
  role: MessageRole;
  content: string;
  name?: string;
}

export interface ToolDefinition {
  name: string;
  description?: string;
  inputSchema: Record<string, unknown>;
}

export interface GenerateRequest {
  model: string;
  messages: WagentMessage[];
  sessionId?: string;
  stream?: boolean;
  tools?: ToolDefinition[];
  requiredCapabilities?: Capability[];
  metadata?: Record<string, unknown>;
}

export type WagentEvent =
  | { type: "text.delta"; text: string }
  | { type: "reasoning.delta"; text: string }
  | { type: "tool.call"; id: string; name: string; arguments: unknown }
  | { type: "citation"; url: string; title?: string }
  | { type: "usage"; inputTokens?: number; outputTokens?: number; totalTokens?: number }
  | { type: "error"; error: string; retryable?: boolean }
  | { type: "done"; providerState?: Record<string, unknown> };

export interface ProviderContext {
  signal?: AbortSignal;
  providerState?: Record<string, unknown>;
}

export interface ProviderModel {
  id: string;
  name?: string;
  capabilities?: Partial<ProviderCapabilities>;
}

export interface WagentProvider {
  readonly id: string;
  readonly name: string;
  readonly capabilities: ProviderCapabilities;
  listModels(): Promise<ProviderModel[]>;
  generate(request: GenerateRequest, context: ProviderContext): AsyncIterable<WagentEvent>;
  dispose?(): Promise<void>;
}

export const capabilities = (value: Partial<ProviderCapabilities> = {}): ProviderCapabilities => ({
  streaming: false,
  tools: false,
  reasoning: false,
  vision: false,
  files: false,
  webSearch: false,
  conversations: false,
  ...value,
});

export function splitModelId(model: string): { providerId?: string; modelId: string } {
  if (model === "auto") return { modelId: "auto" };
  const slash = model.indexOf("/");
  if (slash <= 0) return { modelId: model };
  return { providerId: model.slice(0, slash), modelId: model.slice(slash + 1) };
}
