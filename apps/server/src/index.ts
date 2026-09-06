import { Hono } from "hono";
import { streamSSE } from "hono/streaming";
import { z } from "zod";
import { WagentRuntime, ProviderRegistry } from "../../../packages/runtime/src/index.ts";
import { ChatGPTWebProvider } from "../../../packages/providers/chatgpt-web/src/index.ts";
import { DeepSeekWebProvider } from "../../../packages/providers/deepseek-web/src/index.ts";
import { OpenAICompatibleProvider } from "../../../packages/providers/openai-compatible/src/index.ts";
import { AnthropicProvider } from "../../../packages/providers/anthropic/src/index.ts";

const registry = new ProviderRegistry()
  .register(new ChatGPTWebProvider())
  .register(new DeepSeekWebProvider())
  .register(new OpenAICompatibleProvider())
  .register(new AnthropicProvider());
const runtime = await new WagentRuntime(registry).init();
const app = new Hono();

const requestSchema = z.object({
  model: z.string().default("auto"),
  messages: z.array(z.object({ role: z.enum(["system", "user", "assistant", "tool"]), content: z.string(), name: z.string().optional() })),
  sessionId: z.string().optional(),
  stream: z.boolean().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
  tools: z.array(z.object({ name: z.string(), description: z.string().optional(), inputSchema: z.record(z.string(), z.unknown()) })).optional(),
});

app.get("/health", c => c.json({ ok: true, runtime: "wagent", version: "0.2.0" }));
app.get("/v1/status", c => c.json({ ok: true, providers: registry.list().map(provider => provider.id), sessions: runtime.sessions.list().length }));
app.get("/v1/providers", c => c.json({ data: registry.list().map(provider => ({ id: provider.id, name: provider.name, capabilities: provider.capabilities })) }));
app.get("/v1/skills", c => c.json({ data: runtime.listSkills().map(skill => ({ name: skill.name, description: skill.description, tags: skill.tags })) }));
app.get("/v1/models", async c => {
  const data = (await Promise.all(registry.list().map(async provider => {
    try { return (await provider.listModels()).map(model => ({ id: `${provider.id}/${model.id}`, object: "model", owned_by: provider.id })); }
    catch { return []; }
  }))).flat();
  return c.json({ object: "list", data });
});

app.post("/v1/generate", async c => {
  const parsed = requestSchema.safeParse(await c.req.json());
  if (!parsed.success) return c.json({ error: parsed.error.flatten() }, 400);
  if (parsed.data.stream) return streamSSE(c, async stream => { for await (const event of runtime.generate(parsed.data)) await stream.writeSSE({ event: event.type, data: JSON.stringify(event) }); });
  return c.json(await runtime.text(parsed.data));
});

app.post("/v1/chat", async c => {
  const body = await c.req.json<Record<string, unknown>>();
  if (typeof body.message !== "string" || !body.message.trim()) return c.json({ error: "message is required" }, 400);
  const result = await runtime.text({
    model: typeof body.model === "string" ? body.model : "chatgpt-web/default",
    sessionId: typeof body.session_id === "string" ? body.session_id : undefined,
    messages: [{ role: "user", content: body.message }],
    metadata: {
      attachments: Array.isArray(body.files) ? body.files : undefined,
      webSearch: body.web_search === true,
      newChat: body.new_conversation === true,
      profile: typeof body.profile === "string" ? body.profile : undefined,
    },
  });
  return c.json({ message: result.text, session_id: result.sessionId, reasoning: result.reasoning || undefined });
});

app.post("/v1/chat/completions", async c => {
  const body = await c.req.json<Record<string, unknown>>();
  const parsed = requestSchema.safeParse({ ...body, sessionId: body.session_id });
  if (!parsed.success) return c.json({ error: { message: parsed.error.message, type: "invalid_request_error" } }, 400);

  if (parsed.data.stream) {
    const id = `chatcmpl-${crypto.randomUUID()}`;
    return streamSSE(c, async stream => {
      for await (const event of runtime.generate(parsed.data)) {
        if (event.type !== "text.delta" && event.type !== "reasoning.delta") continue;
        const delta = event.type === "text.delta" ? { content: event.text } : { reasoning_content: event.text };
        await stream.writeSSE({ data: JSON.stringify({ id, object: "chat.completion.chunk", created: Math.floor(Date.now() / 1000), model: parsed.data.model, choices: [{ index: 0, delta, finish_reason: null }] }) });
      }
      await stream.writeSSE({ data: "[DONE]" });
    });
  }

  const result = await runtime.text(parsed.data);
  return c.json({ id: `chatcmpl-${crypto.randomUUID()}`, object: "chat.completion", created: Math.floor(Date.now() / 1000), model: parsed.data.model, choices: [{ index: 0, message: { role: "assistant", content: result.text }, finish_reason: "stop" }], wagent: { session_id: result.sessionId, reasoning: result.reasoning || undefined } });
});

const anthropicContentText = (content: unknown): string => {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content.map(block => {
    if (!block || typeof block !== "object") return "";
    const item = block as Record<string, unknown>;
    if (item.type === "text" && typeof item.text === "string") return item.text;
    if (item.type === "tool_result") return `[tool_result ${String(item.tool_use_id ?? "")}] ${typeof item.content === "string" ? item.content : JSON.stringify(item.content ?? "")}`;
    return "";
  }).filter(Boolean).join("\n");
};

app.post("/v1/messages", async c => {
  const body = await c.req.json<Record<string, unknown>>();
  const model = typeof body.model === "string" ? body.model : "auto";
  const routedModel = model.includes("/") || model === "auto" ? model : `anthropic/${model}`;
  const rawMessages = Array.isArray(body.messages) ? body.messages : [];
  const messages = rawMessages.map(value => {
    const message = value as Record<string, unknown>;
    return { role: message.role === "assistant" ? "assistant" as const : "user" as const, content: anthropicContentText(message.content) };
  });
  const system = anthropicContentText(body.system);
  if (system) messages.unshift({ role: "user", content: `[system]\n${system}\n[/system]` });
  const tools = Array.isArray(body.tools) ? body.tools.flatMap(value => {
    const tool = value as Record<string, unknown>;
    if (typeof tool.name !== "string" || !tool.input_schema || typeof tool.input_schema !== "object") return [];
    return [{ name: tool.name, description: typeof tool.description === "string" ? tool.description : undefined, inputSchema: tool.input_schema as Record<string, unknown> }];
  }) : undefined;
  const request = {
    model: routedModel,
    messages,
    tools,
    stream: body.stream === true,
    metadata: {
      maxTokens: typeof body.max_tokens === "number" ? body.max_tokens : undefined,
      temperature: typeof body.temperature === "number" ? body.temperature : undefined,
    },
  };
  const id = `msg_${crypto.randomUUID().replaceAll("-", "")}`;

  if (body.stream === true) {
    return streamSSE(c, async stream => {
      await stream.writeSSE({ event: "message_start", data: JSON.stringify({ type: "message_start", message: { id, type: "message", role: "assistant", model, content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 0, output_tokens: 0 } } }) });
      let index = 0;
      let textStarted = false;
      let inputTokens = 0;
      let outputTokens = 0;
      for await (const event of runtime.generate(request)) {
        if (event.type === "text.delta" || event.type === "reasoning.delta") {
          if (!textStarted) {
            await stream.writeSSE({ event: "content_block_start", data: JSON.stringify({ type: "content_block_start", index, content_block: { type: "text", text: "" } }) });
            textStarted = true;
          }
          await stream.writeSSE({ event: "content_block_delta", data: JSON.stringify({ type: "content_block_delta", index, delta: { type: "text_delta", text: event.text } }) });
        } else if (event.type === "tool.call") {
          if (textStarted) { await stream.writeSSE({ event: "content_block_stop", data: JSON.stringify({ type: "content_block_stop", index }) }); index += 1; textStarted = false; }
          await stream.writeSSE({ event: "content_block_start", data: JSON.stringify({ type: "content_block_start", index, content_block: { type: "tool_use", id: event.id, name: event.name, input: event.arguments } }) });
          await stream.writeSSE({ event: "content_block_stop", data: JSON.stringify({ type: "content_block_stop", index }) });
          index += 1;
        } else if (event.type === "usage") {
          inputTokens = event.inputTokens ?? inputTokens;
          outputTokens = event.outputTokens ?? outputTokens;
        } else if (event.type === "error") {
          await stream.writeSSE({ event: "error", data: JSON.stringify({ type: "error", error: { type: "api_error", message: event.error } }) });
          return;
        }
      }
      if (textStarted) await stream.writeSSE({ event: "content_block_stop", data: JSON.stringify({ type: "content_block_stop", index }) });
      await stream.writeSSE({ event: "message_delta", data: JSON.stringify({ type: "message_delta", delta: { stop_reason: "end_turn", stop_sequence: null }, usage: { output_tokens: outputTokens } }) });
      await stream.writeSSE({ event: "message_stop", data: JSON.stringify({ type: "message_stop" }) });
    });
  }

  let text = "";
  const content: Array<Record<string, unknown>> = [];
  let inputTokens = 0;
  let outputTokens = 0;
  for await (const event of runtime.generate(request)) {
    if (event.type === "text.delta" || event.type === "reasoning.delta") text += event.text;
    else if (event.type === "tool.call") content.push({ type: "tool_use", id: event.id, name: event.name, input: event.arguments });
    else if (event.type === "usage") { inputTokens = event.inputTokens ?? inputTokens; outputTokens = event.outputTokens ?? outputTokens; }
    else if (event.type === "error") return c.json({ type: "error", error: { type: "api_error", message: event.error } }, 502);
  }
  if (text) content.unshift({ type: "text", text });
  return c.json({ id, type: "message", role: "assistant", model, content, stop_reason: content.some(block => block.type === "tool_use") ? "tool_use" : "end_turn", stop_sequence: null, usage: { input_tokens: inputTokens, output_tokens: outputTokens } });
});

const hostname = process.env.WAGENT_HOST ?? "127.0.0.1";
const port = Number(process.env.WAGENT_PORT ?? 8765);
console.log(`Wagent listening on http://${hostname}:${port}`);
Bun.serve({ hostname, port, fetch: app.fetch });
