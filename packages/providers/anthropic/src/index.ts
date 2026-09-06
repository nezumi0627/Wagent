import { capabilities, type GenerateRequest, type ProviderContext, type ProviderModel, type WagentEvent, type WagentProvider } from "../../../provider-sdk/src/index.ts";

export interface AnthropicProviderOptions {
  id?: string;
  name?: string;
  baseUrl?: string;
  apiKey?: string;
  version?: string;
  headers?: Record<string, string>;
}

type AnthropicStreamEvent = {
  type?: string;
  index?: number;
  delta?: { type?: string; text?: string; thinking?: string; partial_json?: string; stop_reason?: string };
  content_block?: { type?: string; id?: string; name?: string; input?: unknown; text?: string; thinking?: string };
  message?: { usage?: { input_tokens?: number; output_tokens?: number } };
  usage?: { input_tokens?: number; output_tokens?: number };
};

export class AnthropicProvider implements WagentProvider {
  readonly id: string;
  readonly name: string;
  readonly capabilities = capabilities({ streaming: true, tools: true, reasoning: true, vision: true, files: false, webSearch: false, conversations: true });
  readonly #baseUrl: string;
  readonly #apiKey?: string;
  readonly #version: string;
  readonly #headers: Record<string, string>;

  constructor(options: AnthropicProviderOptions = {}) {
    this.id = options.id ?? "anthropic";
    this.name = options.name ?? "Anthropic";
    this.#baseUrl = (options.baseUrl ?? process.env.WAGENT_ANTHROPIC_BASE_URL ?? "https://api.anthropic.com/v1").replace(/\/$/, "");
    this.#apiKey = options.apiKey ?? process.env.WAGENT_ANTHROPIC_API_KEY;
    this.#version = options.version ?? process.env.WAGENT_ANTHROPIC_VERSION ?? "2023-06-01";
    this.#headers = options.headers ?? {};
  }

  async listModels(): Promise<ProviderModel[]> {
    const response = await fetch(`${this.#baseUrl}/models`, { headers: this.headers() });
    if (!response.ok) throw new Error(`Anthropic model list failed: ${response.status}`);
    const body = await response.json() as { data?: Array<{ id: string; display_name?: string }> };
    return (body.data ?? []).map(model => ({ id: model.id, name: model.display_name }));
  }

  async *generate(request: GenerateRequest, context: ProviderContext): AsyncIterable<WagentEvent> {
    const system = request.messages.filter(message => message.role === "system").map(message => message.content).join("\n\n") || undefined;
    const messages = request.messages.filter(message => message.role !== "system").map(message => ({
      role: message.role === "assistant" ? "assistant" : "user",
      content: message.content,
    }));

    const response = await fetch(`${this.#baseUrl}/messages`, {
      method: "POST",
      signal: context.signal,
      headers: { ...this.headers(), "content-type": "application/json" },
      body: JSON.stringify({
        model: request.model,
        max_tokens: Number(request.metadata?.maxTokens ?? request.metadata?.max_tokens ?? 4096),
        system,
        messages,
        stream: true,
        temperature: typeof request.metadata?.temperature === "number" ? request.metadata.temperature : undefined,
        tools: request.tools?.map(tool => ({ name: tool.name, description: tool.description, input_schema: tool.inputSchema })),
      }),
    });

    if (!response.ok || !response.body) {
      yield { type: "error", error: `Anthropic request failed: ${response.status} ${await response.text()}`, retryable: response.status >= 500 || response.status === 429 };
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const toolBlocks = new Map<number, { id: string; name: string; json: string }>();
    let inputTokens: number | undefined;
    let outputTokens: number | undefined;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const dataLine = frame.split("\n").find(line => line.startsWith("data:"));
        if (!dataLine) continue;
        const data = dataLine.slice(5).trim();
        if (!data) continue;
        const event = JSON.parse(data) as AnthropicStreamEvent;

        if (event.type === "message_start") inputTokens = event.message?.usage?.input_tokens ?? inputTokens;
        if (event.type === "message_delta") outputTokens = event.usage?.output_tokens ?? outputTokens;

        if (event.type === "content_block_start" && event.content_block?.type === "tool_use" && typeof event.index === "number") {
          toolBlocks.set(event.index, {
            id: event.content_block.id ?? crypto.randomUUID(),
            name: event.content_block.name ?? "unknown",
            json: JSON.stringify(event.content_block.input ?? {}).replace(/^\{\}$/, ""),
          });
        }

        if (event.type === "content_block_delta") {
          if (event.delta?.type === "text_delta" && typeof event.delta.text === "string") yield { type: "text.delta", text: event.delta.text };
          if (event.delta?.type === "thinking_delta" && typeof event.delta.thinking === "string") yield { type: "reasoning.delta", text: event.delta.thinking };
          if (event.delta?.type === "input_json_delta" && typeof event.index === "number") {
            const tool = toolBlocks.get(event.index);
            if (tool) tool.json += event.delta.partial_json ?? "";
          }
        }

        if (event.type === "content_block_stop" && typeof event.index === "number") {
          const tool = toolBlocks.get(event.index);
          if (tool) {
            let args: unknown = tool.json || {};
            try { args = tool.json ? JSON.parse(tool.json) : {}; } catch { /* keep partial JSON as string */ }
            yield { type: "tool.call", id: tool.id, name: tool.name, arguments: args };
            toolBlocks.delete(event.index);
          }
        }
      }
    }

    if (inputTokens !== undefined || outputTokens !== undefined) {
      yield { type: "usage", inputTokens, outputTokens, totalTokens: (inputTokens ?? 0) + (outputTokens ?? 0) };
    }
    yield { type: "done" };
  }

  private headers(): Record<string, string> {
    return {
      ...(this.#apiKey ? { "x-api-key": this.#apiKey } : {}),
      "anthropic-version": this.#version,
      ...this.#headers,
    };
  }
}
