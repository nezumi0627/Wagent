import { capabilities, type GenerateRequest, type ProviderContext, type ProviderModel, type WagentEvent, type WagentProvider } from "../../../provider-sdk/src/index.ts";

export interface OpenAICompatibleOptions {
  id?: string;
  name?: string;
  baseUrl?: string;
  apiKey?: string;
  headers?: Record<string, string>;
}

export class OpenAICompatibleProvider implements WagentProvider {
  readonly id: string;
  readonly name: string;
  readonly capabilities = capabilities({ streaming: true, tools: true, reasoning: true, vision: true, files: false, webSearch: false, conversations: true });
  readonly #baseUrl: string;
  readonly #apiKey?: string;
  readonly #headers: Record<string, string>;

  constructor(options: OpenAICompatibleOptions = {}) {
    this.id = options.id ?? "openai-compatible";
    this.name = options.name ?? "OpenAI Compatible";
    this.#baseUrl = (options.baseUrl ?? process.env.WAGENT_OPENAI_BASE_URL ?? "https://api.openai.com/v1").replace(/\/$/, "");
    this.#apiKey = options.apiKey ?? process.env.WAGENT_OPENAI_API_KEY;
    this.#headers = options.headers ?? {};
  }

  async listModels(): Promise<ProviderModel[]> {
    const response = await fetch(`${this.#baseUrl}/models`, { headers: this.headers() });
    if (!response.ok) throw new Error(`Model list failed: ${response.status}`);
    const body = await response.json() as { data?: Array<{ id: string }> };
    return (body.data ?? []).map(model => ({ id: model.id }));
  }

  async *generate(request: GenerateRequest, context: ProviderContext): AsyncIterable<WagentEvent> {
    const response = await fetch(`${this.#baseUrl}/chat/completions`, {
      method: "POST",
      signal: context.signal,
      headers: { ...this.headers(), "content-type": "application/json" },
      body: JSON.stringify({
        model: request.model,
        messages: request.messages,
        stream: true,
        tools: request.tools?.map(tool => ({ type: "function", function: { name: tool.name, description: tool.description, parameters: tool.inputSchema } })),
      }),
    });
    if (!response.ok || !response.body) {
      yield { type: "error", error: `OpenAI-compatible request failed: ${response.status} ${await response.text()}`, retryable: response.status >= 500 };
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (!data || data === "[DONE]") continue;
        const chunk = JSON.parse(data) as any;
        const delta = chunk.choices?.[0]?.delta;
        if (typeof delta?.content === "string") yield { type: "text.delta", text: delta.content };
        const reasoning = delta?.reasoning_content ?? delta?.reasoning;
        if (typeof reasoning === "string") yield { type: "reasoning.delta", text: reasoning };
        for (const call of delta?.tool_calls ?? []) {
          yield { type: "tool.call", id: call.id ?? crypto.randomUUID(), name: call.function?.name ?? "unknown", arguments: call.function?.arguments ?? "" };
        }
        if (chunk.usage) yield { type: "usage", inputTokens: chunk.usage.prompt_tokens, outputTokens: chunk.usage.completion_tokens, totalTokens: chunk.usage.total_tokens };
      }
    }
    yield { type: "done" };
  }

  private headers(): Record<string, string> {
    return { ...(this.#apiKey ? { authorization: `Bearer ${this.#apiKey}` } : {}), ...this.#headers };
  }
}
